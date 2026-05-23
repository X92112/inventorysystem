from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Q, F
from django.db import IntegrityError
from django.db.models.deletion import ProtectedError
from django.core.paginator import Paginator

from .models import (
    Category, Supplier, Product,
    StockMovement, PurchaseOrder, PurchaseOrderItem,
)


# ─────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────

def _base_ctx():
    return {
        'low_stock_count': Product.objects.filter(stock__lte=F('min_stock')).count()
    }


# ─────────────────────────────────────────
#  Dashboard
# ─────────────────────────────────────────

@login_required
def dashboard(request):
    total_products  = Product.objects.count()
    low_stock_count = Product.objects.filter(stock__lte=F('min_stock')).count()
    pending_orders  = PurchaseOrder.objects.filter(status='PENDING').count()
    stock_value     = sum(p.stock_value for p in Product.objects.all())

    recent_movements   = StockMovement.objects.select_related('product')[:8]
    low_stock_products = Product.objects.filter(
        stock__lte=F('min_stock')
    ).select_related('category')[:10]

    # Stock per category with percentage for the bar chart
    categories = Category.objects.all()
    max_stock  = max((c.total_stock for c in categories), default=1) or 1
    stock_by_cat = []
    for cat in categories:
        ts = cat.total_stock
        stock_by_cat.append({
            'name':        cat.name,
            'total_stock': ts,
            'percentage':  round(ts / max_stock * 100),
            'color':       cat.color,
        })

    ctx = {
        **_base_ctx(),
        'total_products':     total_products,
        'low_stock_count':    low_stock_count,
        'pending_orders':     pending_orders,
        'stock_value':        stock_value,
        'recent_movements':   recent_movements,
        'low_stock_products': low_stock_products,
        'stock_by_category':  stock_by_cat,
    }
    return render(request, 'inventory/dashboard.html', ctx)


# ─────────────────────────────────────────
#  Products
# ─────────────────────────────────────────

@login_required
def product_list(request):
    qs      = Product.objects.select_related('category', 'supplier').all()
    q       = request.GET.get('q', '').strip()
    cat_id  = request.GET.get('category', '')
    stock_f = request.GET.get('stock', '')

    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(sku__icontains=q))
    if cat_id:
        qs = qs.filter(category_id=cat_id)
    if stock_f == 'out':
        qs = qs.filter(stock=0)
    elif stock_f == 'low':
        qs = qs.filter(stock__gt=0, stock__lte=F('min_stock'))
    elif stock_f == 'ok':
        qs = qs.filter(stock__gt=F('min_stock'))

    paginator = Paginator(qs, 20)
    products  = paginator.get_page(request.GET.get('page'))

    ctx = {
        **_base_ctx(),
        'products':   products,
        'categories': Category.objects.all(),
    }
    return render(request, 'inventory/product_list.html', ctx)


@login_required
def product_detail(request, pk):
    product   = get_object_or_404(Product, pk=pk)
    movements = product.movements.all()[:20]
    ctx = {
        **_base_ctx(),
        'product':   product,
        'movements': movements,
    }
    return render(request, 'inventory/product_detail.html', ctx)


@login_required
def product_create(request):
    categories = Category.objects.all()
    suppliers  = Supplier.objects.all()
    errors     = {}

    if request.method == 'POST':
        data   = request.POST
        errors = _validate_product(data)

        if not errors:
            product = Product.objects.create(
                name        = data['name'].strip(),
                sku         = data['sku'].strip().upper(),
                description = data.get('description', '').strip(),
                category_id = data['category'],
                supplier_id = data.get('supplier') or None,
                price       = data['price'],
                stock       = int(data.get('stock', 0)),
                min_stock   = int(data.get('min_stock', 10)),
            )
            if product.stock > 0:
                StockMovement.objects.create(
                    product       = product,
                    movement_type = 'IN',
                    quantity      = product.stock,
                    note          = 'Initial stock',
                    created_by    = request.user,
                )
            messages.success(request, f'Product "{product.name}" created.')
            return redirect('inventory:product_list')

    ctx = {
        **_base_ctx(),
        'categories': categories,
        'suppliers':  suppliers,
        'form':       _FormProxy(request.POST if request.method == 'POST' else {}),
        'errors':     errors,
    }
    return render(request, 'inventory/product_form.html', ctx)


@login_required
def product_edit(request, pk):
    product    = get_object_or_404(Product, pk=pk)
    categories = Category.objects.all()
    suppliers  = Supplier.objects.all()
    errors     = {}

    if request.method == 'POST':
        data   = request.POST
        errors = _validate_product(data, editing=True)

        if not errors:
            product.name        = data['name'].strip()
            product.sku         = data['sku'].strip().upper()
            product.description = data.get('description', '').strip()
            product.category_id = data['category']
            product.supplier_id = data.get('supplier') or None
            product.price       = data['price']
            product.min_stock   = int(data.get('min_stock', 10))
            product.save()
            messages.success(request, f'Product "{product.name}" updated.')
            return redirect('inventory:product_list')

    ctx = {
        **_base_ctx(),
        'product':    product,
        'categories': categories,
        'suppliers':  suppliers,
        'form': _FormProxy(request.POST if request.method == 'POST' else {
            'name':        product.name,
            'sku':         product.sku,
            'description': product.description,
            'category':    product.category_id,
            'supplier':    product.supplier_id,
            'price':       product.price,
            'stock':       product.stock,
            'min_stock':   product.min_stock,
        }),
        'errors': errors,
    }
    return render(request, 'inventory/product_form.html', ctx)


@login_required
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        name = product.name
        try:
            product.delete()
            messages.success(request, f'Product "{name}" deleted.')
            return redirect('inventory:product_list')
        except ProtectedError:
            messages.error(
                request,
                f'Cannot delete "{name}" because it is linked to one or more orders. '
                f'Please delete or cancel those orders first, then try again.'
            )
            return redirect('inventory:product_detail', pk=pk)
    ctx = {**_base_ctx(), 'product': product}
    return render(request, 'inventory/product_confirm_delete.html', ctx)


# ─────────────────────────────────────────
#  Categories
# ─────────────────────────────────────────

@login_required
def category_list(request):
    categories = Category.objects.all()
    ctx = {**_base_ctx(), 'categories': categories}
    return render(request, 'inventory/category_list.html', ctx)


@login_required
def category_create(request):
    if request.method == 'POST':
        name  = request.POST.get('name', '').strip()
        color = request.POST.get('color', '#378ADD')
        desc  = request.POST.get('description', '').strip()
        if not name:
            messages.error(request, 'Category name is required.')
        elif Category.objects.filter(name=name).exists():
            messages.error(request, 'A category with this name already exists.')
        else:
            Category.objects.create(name=name, color=color, description=desc)
            messages.success(request, f'Category "{name}" created.')
            return redirect('inventory:category_list')
    ctx = {**_base_ctx()}
    return render(request, 'inventory/category_form.html', ctx)


# ─────────────────────────────────────────
#  Stock movements
# ─────────────────────────────────────────

@login_required
def stock_list(request):
    out_of_stock = Product.objects.filter(stock=0).count()
    low_stock    = Product.objects.filter(stock__gt=0, stock__lte=F('min_stock')).count()
    stock_items  = Product.objects.select_related('category').all()

    ctx = {
        **_base_ctx(),
        'stock_items':  stock_items,
        'out_of_stock': out_of_stock,
        'low_stock':    low_stock,
    }
    return render(request, 'inventory/stock_list.html', ctx)


@login_required
def movement_list(request):
    movements = StockMovement.objects.select_related('product', 'created_by').all()
    paginator = Paginator(movements, 25)
    page      = paginator.get_page(request.GET.get('page'))
    ctx = {**_base_ctx(), 'movements': page}
    return render(request, 'inventory/movement_list.html', ctx)


@login_required
def movement_create(request):
    products = Product.objects.all()
    if request.method == 'POST':
        product_id    = request.POST.get('product')
        movement_type = request.POST.get('movement_type')
        quantity      = request.POST.get('quantity', '0')
        note          = request.POST.get('note', '').strip()

        if not all([product_id, movement_type, quantity]):
            messages.error(request, 'All fields are required.')
        else:
            try:
                qty     = int(quantity)
                product = get_object_or_404(Product, pk=product_id)
                if qty <= 0:
                    raise ValueError
                StockMovement.objects.create(
                    product       = product,
                    movement_type = movement_type,
                    quantity      = qty,
                    note          = note,
                    created_by    = request.user,
                )
                messages.success(request, f'Stock movement recorded for "{product.name}".')
                return redirect('inventory:stock_list')
            except (ValueError, TypeError):
                messages.error(request, 'Quantity must be a positive number.')

    ctx = {**_base_ctx(), 'products': products}
    return render(request, 'inventory/movement_form.html', ctx)


# ─────────────────────────────────────────
#  Suppliers
# ─────────────────────────────────────────

@login_required
def supplier_list(request):
    suppliers = Supplier.objects.all()
    ctx = {**_base_ctx(), 'suppliers': suppliers}
    return render(request, 'inventory/supplier_list.html', ctx)


@login_required
def supplier_create(request):
    if request.method == 'POST':
        data = request.POST
        name = data.get('name', '').strip()
        if not name:
            messages.error(request, 'Supplier name is required.')
        else:
            Supplier.objects.create(
                name    = name,
                email   = data.get('email', '').strip(),
                phone   = data.get('phone', '').strip(),
                address = data.get('address', '').strip(),
                notes   = data.get('notes', '').strip(),
            )
            messages.success(request, f'Supplier "{name}" created.')
            return redirect('inventory:supplier_list')
    ctx = {**_base_ctx()}
    return render(request, 'inventory/supplier_form.html', ctx)


@login_required
def supplier_delete(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    if request.method == 'POST':
        name = supplier.name
        try:
            supplier.delete()
            messages.success(request, f'Supplier "{name}" deleted.')
            return redirect('inventory:supplier_list')
        except ProtectedError:
            messages.error(
                request,
                f'Cannot delete "{name}" because it is linked to one or more orders. '
                f'Please delete those orders first, then try again.'
            )
            return redirect('inventory:supplier_list')
    ctx = {**_base_ctx(), 'supplier': supplier}
    return render(request, 'inventory/supplier_confirm_delete.html', ctx)


# ─────────────────────────────────────────
#  Purchase orders
# ─────────────────────────────────────────

@login_required
def order_list(request):
    qs     = PurchaseOrder.objects.select_related('supplier').prefetch_related('items')
    status = request.GET.get('status', '')
    if status:
        qs = qs.filter(status=status)
    ctx = {**_base_ctx(), 'orders': qs}
    return render(request, 'inventory/order_list.html', ctx)


@login_required
def order_detail(request, pk):
    order = get_object_or_404(
        PurchaseOrder.objects.select_related('supplier')
                             .prefetch_related('items__product'),
        pk=pk
    )
    ctx = {**_base_ctx(), 'order': order}
    return render(request, 'inventory/order_detail.html', ctx)


@login_required
def order_create(request):
    suppliers = Supplier.objects.all()
    products  = Product.objects.all()

    if request.method == 'POST':
        supplier_id = request.POST.get('supplier')
        notes       = request.POST.get('notes', '').strip()
        prod_ids    = request.POST.getlist('product_id')
        quantities  = request.POST.getlist('quantity')
        prices      = request.POST.getlist('unit_price')

        if not supplier_id:
            messages.error(request, 'Please select a supplier.')
        elif not prod_ids:
            messages.error(request, 'Add at least one product line.')
        else:
            order = PurchaseOrder.objects.create(
                supplier_id = supplier_id,
                notes       = notes,
                created_by  = request.user,
            )
            for pid, qty, price in zip(prod_ids, quantities, prices):
                try:
                    PurchaseOrderItem.objects.create(
                        order_id   = order.pk,
                        product_id = pid,
                        quantity   = int(qty),
                        unit_price = price,
                    )
                except Exception:
                    pass
            messages.success(request, f'Order PO-{order.pk:04d} created.')
            return redirect('inventory:order_detail', pk=order.pk)

    ctx = {
        **_base_ctx(),
        'suppliers': suppliers,
        'products':  products,
    }
    return render(request, 'inventory/order_form.html', ctx)


@login_required
def order_update_status(request, pk):
    order  = get_object_or_404(PurchaseOrder, pk=pk)
    status = request.POST.get('status')
    valid  = [s[0] for s in PurchaseOrder.STATUS_CHOICES]

    if request.method == 'POST' and status in valid:
        order.status = status
        order.save()
        if status == 'RECEIVED':
            for item in order.items.all():
                StockMovement.objects.create(
                    product       = item.product,
                    movement_type = 'IN',
                    quantity      = item.quantity,
                    note          = f'Received from PO-{order.pk:04d}',
                    created_by    = request.user,
                )
        messages.success(request, f'Order status updated to "{order.get_status_display()}".')
    return redirect('inventory:order_detail', pk=pk)


@login_required
def order_delete(request, pk):
    order = get_object_or_404(PurchaseOrder, pk=pk)
    if request.method == 'POST':
        label = f'PO-{order.pk:04d}'
        order.delete()
        messages.success(request, f'Order {label} deleted.')
        return redirect('inventory:order_list')
    ctx = {**_base_ctx(), 'order': order}
    return render(request, 'inventory/order_confirm_delete.html', ctx)


# ─────────────────────────────────────────
#  Internal helpers
# ─────────────────────────────────────────

def _validate_product(data, editing=False):
    errors = {}
    if not data.get('name', '').strip():
        errors['name'] = 'Name is required.'
    if not data.get('sku', '').strip():
        errors['sku'] = 'SKU is required.'
    if not data.get('category'):
        errors['category'] = 'Category is required.'
    try:
        p = float(data.get('price', ''))
        if p < 0:
            raise ValueError
    except (ValueError, TypeError):
        errors['price'] = 'Enter a valid price.'
    return errors


class _FormProxy:
    """Thin dict wrapper so templates can use form.field_name.value syntax."""
    def __init__(self, data):
        self._data = data

    def __getattr__(self, name):
        val = self._data.get(name, '')

        class _Field:
            def __init__(self, v):
                self._v = v
                self.errors = []

            def value(self):
                return self._v

        return _Field(val)
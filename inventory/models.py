from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Category(models.Model):
    name        = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    color       = models.CharField(max_length=20, default='#378ADD',
                                   help_text='Hex color for dashboard bar')
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'categories'
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def total_stock(self):
        return self.product_set.aggregate(
            total=models.Sum('stock')
        )['total'] or 0


class Supplier(models.Model):
    name    = models.CharField(max_length=200)
    email   = models.EmailField(blank=True)
    phone   = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    notes   = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Product(models.Model):
    name        = models.CharField(max_length=200)
    sku         = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    category    = models.ForeignKey(Category, on_delete=models.PROTECT)
    supplier    = models.ForeignKey(Supplier, on_delete=models.SET_NULL,
                                    null=True, blank=True)
    price       = models.DecimalField(max_digits=10, decimal_places=2)
    stock       = models.PositiveIntegerField(default=0)
    min_stock   = models.PositiveIntegerField(default=10,
                                              help_text='Alert threshold')
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.sku})'

    @property
    def status(self):
        if self.stock == 0:
            return 'out'
        if self.stock <= self.min_stock:
            return 'low'
        return 'ok'

    @property
    def stock_value(self):
        return self.price * self.stock


class StockMovement(models.Model):
    MOVEMENT_TYPES = [
        ('IN',     'Stock In'),
        ('OUT',    'Stock Out'),
        ('ADJUST', 'Adjustment'),
    ]

    product       = models.ForeignKey(Product, on_delete=models.CASCADE,
                                      related_name='movements')
    movement_type = models.CharField(max_length=10, choices=MOVEMENT_TYPES)
    quantity      = models.PositiveIntegerField()
    note          = models.CharField(max_length=300, blank=True)
    created_by    = models.ForeignKey(User, on_delete=models.SET_NULL,
                                      null=True, blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.movement_type} {self.quantity} × {self.product.name}'

    def save(self, *args, **kwargs):
        """Update product stock when a movement is saved."""
        if self.movement_type == 'IN':
            self.product.stock += self.quantity
        elif self.movement_type == 'OUT':
            self.product.stock = max(0, self.product.stock - self.quantity)
        elif self.movement_type == 'ADJUST':
            self.product.stock = self.quantity   # set absolute value
        self.product.save()
        super().save(*args, **kwargs)


class PurchaseOrder(models.Model):
    STATUS_CHOICES = [
        ('PENDING',   'Pending'),
        ('SHIPPED',   'Shipped'),
        ('RECEIVED',  'Received'),
        ('CANCELLED', 'Cancelled'),
    ]

    supplier   = models.ForeignKey(Supplier, on_delete=models.PROTECT,
                                   related_name='orders')
    status     = models.CharField(max_length=20, choices=STATUS_CHOICES,
                                  default='PENDING')
    notes      = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL,
                                   null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'PO-{self.pk:04d} — {self.supplier.name}'

    @property
    def total(self):
        return sum(item.line_total for item in self.items.all())


class PurchaseOrderItem(models.Model):
    order      = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE,
                                   related_name='items')
    product    = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity   = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f'{self.quantity} × {self.product.name}'

    @property
    def line_total(self):
        return self.unit_price * self.quantity
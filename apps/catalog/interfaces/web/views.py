"""
Catalog web views.

CBVs over our ORM models, one simple form-per-entity for master data, and a
richer ProductForm that honors the domain's type/combo semantics.

All write operations:
  - require login (LoginRequiredMixin),
  - require the corresponding Permission Registry code (PermissionRequiredMixin
    mapped via our `catalog.<resource>.<action>` convention),
  - operate in the current TenantContext — TenantOwnedModel.save() handles
    stamping organization_id automatically.

Notes on Django form styling:
  - We attach Bootstrap's `form-control` to every widget in __init__ so the
    generic form_field.html partial doesn't have to special-case widget types.
"""
from __future__ import annotations

from django import forms
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from common.forms import BootstrapFormMixin
from apps.catalog.infrastructure.models import (
    Brand,
    Category,
    Product,
    ProductTypeChoices,
    Tax,
    Unit,
)


# ---------------------------------------------------------------------------
# Form mixin — paint every widget with Bootstrap classes
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Category
# ---------------------------------------------------------------------------
class CategoryForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Category
        fields = ["code", "name", "is_active"]


class CategoryListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "catalog.categories.view"
    model = Category
    template_name = "catalog/category/list.html"
    context_object_name = "object_list"
    paginate_by = 25
    ordering = "code"


class CategoryCreateView(LoginRequiredMixin, PermissionRequiredMixin,
                         SuccessMessageMixin, CreateView):
    permission_required = "catalog.categories.create"
    model = Category
    form_class = CategoryForm
    template_name = "catalog/category/form.html"
    success_url = reverse_lazy("catalog:category_list")
    success_message = "Category created."


class CategoryUpdateView(LoginRequiredMixin, PermissionRequiredMixin,
                         SuccessMessageMixin, UpdateView):
    permission_required = "catalog.categories.update"
    model = Category
    form_class = CategoryForm
    template_name = "catalog/category/form.html"
    success_url = reverse_lazy("catalog:category_list")
    success_message = "Category updated."


class CategoryDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    permission_required = "catalog.categories.deactivate"
    model = Category
    template_name = "_partials/confirm_delete.html"
    success_url = reverse_lazy("catalog:category_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cancel_url"] = self.success_url
        return ctx


# ---------------------------------------------------------------------------
# Brand
# ---------------------------------------------------------------------------
class BrandForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Brand
        fields = ["code", "name", "is_active"]


class BrandListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "catalog.brands.view"
    model = Brand
    template_name = "catalog/brand/list.html"
    paginate_by = 25
    ordering = "code"


class BrandCreateView(LoginRequiredMixin, PermissionRequiredMixin,
                      SuccessMessageMixin, CreateView):
    permission_required = "catalog.brands.create"
    model = Brand
    form_class = BrandForm
    template_name = "catalog/brand/form.html"
    success_url = reverse_lazy("catalog:brand_list")
    success_message = "Brand created."


class BrandUpdateView(LoginRequiredMixin, PermissionRequiredMixin,
                      SuccessMessageMixin, UpdateView):
    permission_required = "catalog.brands.update"
    model = Brand
    form_class = BrandForm
    template_name = "catalog/brand/form.html"
    success_url = reverse_lazy("catalog:brand_list")
    success_message = "Brand updated."


class BrandDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    permission_required = "catalog.brands.deactivate"
    model = Brand
    template_name = "_partials/confirm_delete.html"
    success_url = reverse_lazy("catalog:brand_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cancel_url"] = self.success_url
        return ctx


# ---------------------------------------------------------------------------
# Unit
# ---------------------------------------------------------------------------
class UnitForm(BootstrapFormMixin, forms.ModelForm):
    # Declared at class-build time with `all_tenants()` so the ModelForm
    # metaclass doesn't trip the TenantContext guard by calling `.all()` on
    # the FK's default manager during import. See apps.tenancy.
    base_unit = forms.ModelChoiceField(
        queryset=Unit.objects.all_tenants(),
        required=False,
    )

    class Meta:
        model = Unit
        fields = ["code", "name", "base_unit", "conversion_factor", "is_active"]


class UnitListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "catalog.units.view"
    model = Unit
    template_name = "catalog/unit/list.html"
    paginate_by = 25
    ordering = "code"


class UnitCreateView(LoginRequiredMixin, PermissionRequiredMixin,
                     SuccessMessageMixin, CreateView):
    permission_required = "catalog.units.create"
    model = Unit
    form_class = UnitForm
    template_name = "catalog/unit/form.html"
    success_url = reverse_lazy("catalog:unit_list")
    success_message = "Unit created."


class UnitUpdateView(LoginRequiredMixin, PermissionRequiredMixin,
                     SuccessMessageMixin, UpdateView):
    permission_required = "catalog.units.update"
    model = Unit
    form_class = UnitForm
    template_name = "catalog/unit/form.html"
    success_url = reverse_lazy("catalog:unit_list")
    success_message = "Unit updated."


# ---------------------------------------------------------------------------
# Tax
# ---------------------------------------------------------------------------
class TaxForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Tax
        fields = ["code", "name", "rate_percent", "is_active"]


class TaxListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "catalog.taxes.view"
    model = Tax
    template_name = "catalog/tax/list.html"
    paginate_by = 25
    ordering = "code"


class TaxCreateView(LoginRequiredMixin, PermissionRequiredMixin,
                    SuccessMessageMixin, CreateView):
    permission_required = "catalog.taxes.create"
    model = Tax
    form_class = TaxForm
    template_name = "catalog/tax/form.html"
    success_url = reverse_lazy("catalog:tax_list")
    success_message = "Tax created."


class TaxUpdateView(LoginRequiredMixin, PermissionRequiredMixin,
                    SuccessMessageMixin, UpdateView):
    permission_required = "catalog.taxes.update"
    model = Tax
    form_class = TaxForm
    template_name = "catalog/tax/form.html"
    success_url = reverse_lazy("catalog:tax_list")
    success_message = "Tax updated."


# ---------------------------------------------------------------------------
# Product
# ---------------------------------------------------------------------------
class ProductForm(BootstrapFormMixin, forms.ModelForm):
    """
    Product form.

    Carries every field the legacy product/create screen did. Combo recipes
    are NOT edited here — they have their own form/view because they must
    reference other products that already exist. The submit view for combos
    uses the catalog application's `CreateProduct` use case which atomically
    creates the product + recipe.
    """

    # See UnitForm — FKs are declared at class-build time with all_tenants()
    # so ModelForm metaclass doesn't accidentally access an un-set tenant
    # context during import.
    category = forms.ModelChoiceField(queryset=Category.objects.all_tenants(), required=False)
    brand = forms.ModelChoiceField(queryset=Brand.objects.all_tenants(), required=False)
    unit = forms.ModelChoiceField(queryset=Unit.objects.all_tenants())
    tax = forms.ModelChoiceField(queryset=Tax.objects.all_tenants(), required=False)

    class Meta:
        model = Product
        fields = [
            "code", "name", "type",
            "category", "brand", "unit", "tax",
            "cost", "price", "currency_code",
            "alert_quantity", "description",
            "barcode_symbology", "is_active",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "type": forms.Select(choices=ProductTypeChoices.choices),
        }


class ProductListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "catalog.products.view"
    model = Product
    template_name = "catalog/product/list.html"
    paginate_by = 25
    ordering = "code"

    def get_queryset(self):
        return (
            super().get_queryset()
            .select_related("category", "brand", "unit", "tax")
        )


class ProductCreateView(LoginRequiredMixin, PermissionRequiredMixin,
                        SuccessMessageMixin, CreateView):
    permission_required = "catalog.products.create"
    model = Product
    form_class = ProductForm
    template_name = "catalog/product/form.html"
    success_url = reverse_lazy("catalog:product_list")
    success_message = "Product created."


class ProductUpdateView(LoginRequiredMixin, PermissionRequiredMixin,
                        SuccessMessageMixin, UpdateView):
    permission_required = "catalog.products.update"
    model = Product
    form_class = ProductForm
    template_name = "catalog/product/form.html"
    success_url = reverse_lazy("catalog:product_list")
    success_message = "Product updated."


class ProductDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    permission_required = "catalog.products.deactivate"
    model = Product
    template_name = "_partials/confirm_delete.html"
    success_url = reverse_lazy("catalog:product_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cancel_url"] = self.success_url
        return ctx

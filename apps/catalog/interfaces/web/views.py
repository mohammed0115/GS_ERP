"""
Catalog web views.

CBVs over our ORM models, one simple form-per-entity for master data, and a
richer ProductForm that honors the domain's type/combo semantics.

All write operations:
  - require login (LoginRequiredMixin),
  - require the corresponding Permission Registry code (OrgPermissionRequiredMixin
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
from common.mixins import OrgPermissionRequiredMixin
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


class CategoryListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
    permission_required = "catalog.categories.view"
    model = Category
    template_name = "catalog/category/list.html"
    context_object_name = "object_list"
    paginate_by = 25
    ordering = "code"


class CategoryCreateView(LoginRequiredMixin, OrgPermissionRequiredMixin,
                         SuccessMessageMixin, CreateView):
    permission_required = "catalog.categories.create"
    model = Category
    form_class = CategoryForm
    template_name = "catalog/category/form.html"
    success_url = reverse_lazy("catalog:category_list")
    success_message = "Category created."


class CategoryUpdateView(LoginRequiredMixin, OrgPermissionRequiredMixin,
                         SuccessMessageMixin, UpdateView):
    permission_required = "catalog.categories.update"
    model = Category
    form_class = CategoryForm
    template_name = "catalog/category/form.html"
    success_url = reverse_lazy("catalog:category_list")
    success_message = "Category updated."


class CategoryDeleteView(LoginRequiredMixin, OrgPermissionRequiredMixin, DeleteView):
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


class BrandListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
    permission_required = "catalog.brands.view"
    model = Brand
    template_name = "catalog/brand/list.html"
    paginate_by = 25
    ordering = "code"


class BrandCreateView(LoginRequiredMixin, OrgPermissionRequiredMixin,
                      SuccessMessageMixin, CreateView):
    permission_required = "catalog.brands.create"
    model = Brand
    form_class = BrandForm
    template_name = "catalog/brand/form.html"
    success_url = reverse_lazy("catalog:brand_list")
    success_message = "Brand created."


class BrandUpdateView(LoginRequiredMixin, OrgPermissionRequiredMixin,
                      SuccessMessageMixin, UpdateView):
    permission_required = "catalog.brands.update"
    model = Brand
    form_class = BrandForm
    template_name = "catalog/brand/form.html"
    success_url = reverse_lazy("catalog:brand_list")
    success_message = "Brand updated."


class BrandDeleteView(LoginRequiredMixin, OrgPermissionRequiredMixin, DeleteView):
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


class UnitListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
    permission_required = "catalog.units.view"
    model = Unit
    template_name = "catalog/unit/list.html"
    paginate_by = 25
    ordering = "code"


class UnitCreateView(LoginRequiredMixin, OrgPermissionRequiredMixin,
                     SuccessMessageMixin, CreateView):
    permission_required = "catalog.units.create"
    model = Unit
    form_class = UnitForm
    template_name = "catalog/unit/form.html"
    success_url = reverse_lazy("catalog:unit_list")
    success_message = "Unit created."


class UnitUpdateView(LoginRequiredMixin, OrgPermissionRequiredMixin,
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


class TaxListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
    permission_required = "catalog.taxes.view"
    model = Tax
    template_name = "catalog/tax/list.html"
    paginate_by = 25
    ordering = "code"


class TaxCreateView(LoginRequiredMixin, OrgPermissionRequiredMixin,
                    SuccessMessageMixin, CreateView):
    permission_required = "catalog.taxes.create"
    model = Tax
    form_class = TaxForm
    template_name = "catalog/tax/form.html"
    success_url = reverse_lazy("catalog:tax_list")
    success_message = "Tax created."


class TaxUpdateView(LoginRequiredMixin, OrgPermissionRequiredMixin,
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


class ProductListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
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


class ProductCreateView(LoginRequiredMixin, OrgPermissionRequiredMixin,
                        SuccessMessageMixin, CreateView):
    permission_required = "catalog.products.create"
    model = Product
    form_class = ProductForm
    template_name = "catalog/product/form.html"
    success_url = reverse_lazy("catalog:product_list")
    success_message = "Product created."


class ProductUpdateView(LoginRequiredMixin, OrgPermissionRequiredMixin,
                        SuccessMessageMixin, UpdateView):
    permission_required = "catalog.products.update"
    model = Product
    form_class = ProductForm
    template_name = "catalog/product/form.html"
    success_url = reverse_lazy("catalog:product_list")
    success_message = "Product updated."


class ProductDeleteView(LoginRequiredMixin, OrgPermissionRequiredMixin, DeleteView):
    permission_required = "catalog.products.deactivate"
    model = Product
    template_name = "_partials/confirm_delete.html"
    success_url = reverse_lazy("catalog:product_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cancel_url"] = self.success_url
        return ctx


# ---------------------------------------------------------------------------
# Barcode PDF generator (Gap 5)
# ---------------------------------------------------------------------------
from django.views import View as DjangoView  # noqa: E402


class PrintBarcodeView(LoginRequiredMixin, OrgPermissionRequiredMixin, DjangoView):
    """
    GET  — render a product-picker form.
    POST — generate and return a PDF barcode sheet.

    POST params:
      product_ids  — repeated form field with product PKs
      page_size    — A4 or Letter (default A4)
      copies       — label copies per product (default 1)
    """
    permission_required = "catalog.products.view"

    def get(self, request):
        from django.shortcuts import render
        products = Product.objects.filter(is_active=True).order_by("code")
        return render(request, "catalog/product/print_barcode.html", {
            "products": products,
        })

    def post(self, request):
        from apps.catalog.application.services.barcode_renderer import (
            BarcodeLabel, render_barcode_sheet,
        )
        from django.http import HttpResponse
        from django.contrib import messages

        product_ids_raw = request.POST.getlist("product_ids")
        page_size = request.POST.get("page_size", "A4").upper()
        if page_size not in ("A4", "LETTER"):
            page_size = "A4"

        try:
            copies = max(1, int(request.POST.get("copies", 1)))
        except (ValueError, TypeError):
            copies = 1

        if not product_ids_raw:
            messages.error(request, "Select at least one product.")
            return self.get(request)

        pks = [int(pid) for pid in product_ids_raw if str(pid).isdigit()]
        products = Product.objects.filter(pk__in=pks, is_active=True)

        labels: list[BarcodeLabel] = []
        for product in products:
            barcode_value = product.barcode or product.code
            for _ in range(copies):
                labels.append(BarcodeLabel(
                    product_code=product.code,
                    product_name=product.name,
                    barcode_value=barcode_value,
                    symbology=product.barcode_symbology or "CODE128",
                    price=str(product.price) if product.price else "",
                ))

        if not labels:
            messages.error(request, "No valid products selected.")
            return self.get(request)

        try:
            pdf_bytes = render_barcode_sheet(labels, page_size=page_size)  # type: ignore[arg-type]
        except ImportError as exc:
            messages.error(request, str(exc))
            return self.get(request)

        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = 'attachment; filename="barcodes.pdf"'
        return response


# ---------------------------------------------------------------------------
# CSV import/export (legacy parity)
# ---------------------------------------------------------------------------
class CSVImportForm(BootstrapFormMixin, forms.Form):
    file = forms.FileField(
        label="CSV file",
        help_text="Upload a CSV file with a header row (UTF-8 recommended).",
    )
    update_existing = forms.BooleanField(
        required=False,
        initial=True,
        label="Update existing records",
        help_text="If unchecked, rows with an existing code will be skipped.",
    )


class _CSVExportBaseView(LoginRequiredMixin, OrgPermissionRequiredMixin, DjangoView):
    filename_prefix: str = "export"

    def _template_only(self, request) -> bool:
        return request.GET.get("template") in {"1", "true", "yes"}

    def _response(self, *, content: bytes, filename: str):
        from django.http import HttpResponse
        resp = HttpResponse(content, content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = f'attachment; filename="{filename}"'
        return resp


class ProductCSVExportView(_CSVExportBaseView):
    permission_required = "catalog.products.export"
    filename_prefix = "products"

    def get(self, request):
        from apps.catalog.application.services.csv_io import export_filename, export_products_csv

        content = export_products_csv(template_only=self._template_only(request))
        return self._response(content=content, filename=export_filename(self.filename_prefix))


class ProductCSVImportView(LoginRequiredMixin, OrgPermissionRequiredMixin, DjangoView):
    permission_required = "catalog.products.import"
    template_name = "_generic/import_csv.html"

    def get(self, request):
        from django.urls import reverse

        form = CSVImportForm()
        return self._render(request, form=form, import_errors=None, template_url=reverse("catalog:product_export") + "?template=1")

    def post(self, request):
        from django.contrib import messages
        from django.shortcuts import redirect
        from apps.catalog.application.services.csv_io import import_products_csv

        form = CSVImportForm(request.POST, request.FILES)
        if not form.is_valid():
            return self._render(request, form=form, import_errors=None, template_url=None)

        csv_data = form.cleaned_data["file"].read()
        update_existing = bool(form.cleaned_data.get("update_existing"))
        result = import_products_csv(csv_data=csv_data, update_existing=update_existing)

        if result.errors:
            messages.error(request, f"Imported with errors: created={result.created}, updated={result.updated}, skipped={result.skipped}.")
            return self._render(request, form=form, import_errors=result.errors, template_url=None)

        messages.success(request, f"Import complete: created={result.created}, updated={result.updated}, skipped={result.skipped}.")
        return redirect("catalog:product_list")

    def _render(self, request, *, form, import_errors, template_url):
        from django.shortcuts import render
        from django.urls import reverse

        return render(request, self.template_name, {
            "title": "Import Products",
            "subtitle": "Upload a CSV file to create/update products",
            "back_url": reverse("catalog:product_list"),
            "template_url": template_url,
            "expected_headers": [
                "code", "name", "type", "category_code", "brand_code", "unit_code", "tax_code",
                "cost", "price", "currency_code", "alert_quantity", "description", "barcode_symbology", "is_active",
            ],
            "header_notes": "You may also use legacy columns like category, brand, unitcode, productdetails.",
            "form": form,
            "import_errors": import_errors,
        })


class CategoryCSVExportView(_CSVExportBaseView):
    permission_required = "catalog.categories.export"
    filename_prefix = "categories"

    def get(self, request):
        from apps.catalog.application.services.csv_io import export_categories_csv, export_filename

        content = export_categories_csv(template_only=self._template_only(request))
        return self._response(content=content, filename=export_filename(self.filename_prefix))


class CategoryCSVImportView(LoginRequiredMixin, OrgPermissionRequiredMixin, DjangoView):
    permission_required = "catalog.categories.import"
    template_name = "_generic/import_csv.html"

    def get(self, request):
        from django.urls import reverse

        form = CSVImportForm()
        return self._render(request, form=form, import_errors=None, template_url=reverse("catalog:category_export") + "?template=1")

    def post(self, request):
        from django.contrib import messages
        from django.shortcuts import redirect
        from apps.catalog.application.services.csv_io import import_categories_csv

        form = CSVImportForm(request.POST, request.FILES)
        if not form.is_valid():
            return self._render(request, form=form, import_errors=None, template_url=None)

        csv_data = form.cleaned_data["file"].read()
        update_existing = bool(form.cleaned_data.get("update_existing"))
        result = import_categories_csv(csv_data=csv_data, update_existing=update_existing)

        if result.errors:
            messages.error(request, f"Imported with errors: created={result.created}, updated={result.updated}, skipped={result.skipped}.")
            return self._render(request, form=form, import_errors=result.errors, template_url=None)

        messages.success(request, f"Import complete: created={result.created}, updated={result.updated}, skipped={result.skipped}.")
        return redirect("catalog:category_list")

    def _render(self, request, *, form, import_errors, template_url):
        from django.shortcuts import render
        from django.urls import reverse

        return render(request, self.template_name, {
            "title": "Import Categories",
            "subtitle": "Upload a CSV file to create/update categories",
            "back_url": reverse("catalog:category_list"),
            "template_url": template_url,
            "expected_headers": ["code", "name", "parent_code", "is_active"],
            "header_notes": "If code is blank, it will be generated from name. Legacy column: parentcategory.",
            "form": form,
            "import_errors": import_errors,
        })


class BrandCSVExportView(_CSVExportBaseView):
    permission_required = "catalog.brands.export"
    filename_prefix = "brands"

    def get(self, request):
        from apps.catalog.application.services.csv_io import export_brands_csv, export_filename

        content = export_brands_csv(template_only=self._template_only(request))
        return self._response(content=content, filename=export_filename(self.filename_prefix))


class BrandCSVImportView(LoginRequiredMixin, OrgPermissionRequiredMixin, DjangoView):
    permission_required = "catalog.brands.import"
    template_name = "_generic/import_csv.html"

    def get(self, request):
        from django.urls import reverse

        form = CSVImportForm()
        return self._render(request, form=form, import_errors=None, template_url=reverse("catalog:brand_export") + "?template=1")

    def post(self, request):
        from django.contrib import messages
        from django.shortcuts import redirect
        from apps.catalog.application.services.csv_io import import_brands_csv

        form = CSVImportForm(request.POST, request.FILES)
        if not form.is_valid():
            return self._render(request, form=form, import_errors=None, template_url=None)

        csv_data = form.cleaned_data["file"].read()
        update_existing = bool(form.cleaned_data.get("update_existing"))
        result = import_brands_csv(csv_data=csv_data, update_existing=update_existing)

        if result.errors:
            messages.error(request, f"Imported with errors: created={result.created}, updated={result.updated}, skipped={result.skipped}.")
            return self._render(request, form=form, import_errors=result.errors, template_url=None)

        messages.success(request, f"Import complete: created={result.created}, updated={result.updated}, skipped={result.skipped}.")
        return redirect("catalog:brand_list")

    def _render(self, request, *, form, import_errors, template_url):
        from django.shortcuts import render
        from django.urls import reverse

        return render(request, self.template_name, {
            "title": "Import Brands",
            "subtitle": "Upload a CSV file to create/update brands",
            "back_url": reverse("catalog:brand_list"),
            "template_url": template_url,
            "expected_headers": ["code", "name", "is_active"],
            "header_notes": "If code is blank, it will be generated from name. Legacy column: title.",
            "form": form,
            "import_errors": import_errors,
        })


class UnitCSVExportView(_CSVExportBaseView):
    permission_required = "catalog.units.export"
    filename_prefix = "units"

    def get(self, request):
        from apps.catalog.application.services.csv_io import export_filename, export_units_csv

        content = export_units_csv(template_only=self._template_only(request))
        return self._response(content=content, filename=export_filename(self.filename_prefix))


class UnitCSVImportView(LoginRequiredMixin, OrgPermissionRequiredMixin, DjangoView):
    permission_required = "catalog.units.import"
    template_name = "_generic/import_csv.html"

    def get(self, request):
        from django.urls import reverse

        form = CSVImportForm()
        return self._render(request, form=form, import_errors=None, template_url=reverse("catalog:unit_export") + "?template=1")

    def post(self, request):
        from django.contrib import messages
        from django.shortcuts import redirect
        from apps.catalog.application.services.csv_io import import_units_csv

        form = CSVImportForm(request.POST, request.FILES)
        if not form.is_valid():
            return self._render(request, form=form, import_errors=None, template_url=None)

        csv_data = form.cleaned_data["file"].read()
        update_existing = bool(form.cleaned_data.get("update_existing"))
        result = import_units_csv(csv_data=csv_data, update_existing=update_existing)

        if result.errors:
            messages.error(request, f"Imported with errors: created={result.created}, updated={result.updated}, skipped={result.skipped}.")
            return self._render(request, form=form, import_errors=result.errors, template_url=None)

        messages.success(request, f"Import complete: created={result.created}, updated={result.updated}, skipped={result.skipped}.")
        return redirect("catalog:unit_list")

    def _render(self, request, *, form, import_errors, template_url):
        from django.shortcuts import render
        from django.urls import reverse

        return render(request, self.template_name, {
            "title": "Import Units",
            "subtitle": "Upload a CSV file to create/update units of measure",
            "back_url": reverse("catalog:unit_list"),
            "template_url": template_url,
            "expected_headers": ["code", "name", "base_unit_code", "conversion_factor", "is_active"],
            "header_notes": "Legacy columns supported: baseunit, operator, operationvalue.",
            "form": form,
            "import_errors": import_errors,
        })


class TaxCSVExportView(_CSVExportBaseView):
    permission_required = "catalog.taxes.export"
    filename_prefix = "taxes"

    def get(self, request):
        from apps.catalog.application.services.csv_io import export_filename, export_taxes_csv

        content = export_taxes_csv(template_only=self._template_only(request))
        return self._response(content=content, filename=export_filename(self.filename_prefix))


class TaxCSVImportView(LoginRequiredMixin, OrgPermissionRequiredMixin, DjangoView):
    permission_required = "catalog.taxes.import"
    template_name = "_generic/import_csv.html"

    def get(self, request):
        from django.urls import reverse

        form = CSVImportForm()
        return self._render(request, form=form, import_errors=None, template_url=reverse("catalog:tax_export") + "?template=1")

    def post(self, request):
        from django.contrib import messages
        from django.shortcuts import redirect
        from apps.catalog.application.services.csv_io import import_taxes_csv

        form = CSVImportForm(request.POST, request.FILES)
        if not form.is_valid():
            return self._render(request, form=form, import_errors=None, template_url=None)

        csv_data = form.cleaned_data["file"].read()
        update_existing = bool(form.cleaned_data.get("update_existing"))
        result = import_taxes_csv(csv_data=csv_data, update_existing=update_existing)

        if result.errors:
            messages.error(request, f"Imported with errors: created={result.created}, updated={result.updated}, skipped={result.skipped}.")
            return self._render(request, form=form, import_errors=result.errors, template_url=None)

        messages.success(request, f"Import complete: created={result.created}, updated={result.updated}, skipped={result.skipped}.")
        return redirect("catalog:tax_list")

    def _render(self, request, *, form, import_errors, template_url):
        from django.shortcuts import render
        from django.urls import reverse

        return render(request, self.template_name, {
            "title": "Import Taxes",
            "subtitle": "Upload a CSV file to create/update tax codes",
            "back_url": reverse("catalog:tax_list"),
            "template_url": template_url,
            "expected_headers": ["code", "name", "rate_percent", "is_active"],
            "header_notes": "Legacy columns supported: rate.",
            "form": form,
            "import_errors": import_errors,
        })

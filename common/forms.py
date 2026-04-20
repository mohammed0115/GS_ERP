"""
Shared form helpers.

`BootstrapFormMixin` paints every widget in a ModelForm with the Bootstrap 4
classes the templates expect. Concrete forms in each app's
`interfaces/web/views.py` import this instead of redefining it.

Usage:
    from common.forms import BootstrapFormMixin

    class ProductForm(BootstrapFormMixin, forms.ModelForm):
        class Meta:
            model = Product
            fields = [...]
"""
from __future__ import annotations

from django import forms


class BootstrapFormMixin:
    """Attach Bootstrap 4 CSS classes to every widget in the form.

    Must come BEFORE `forms.ModelForm` in the MRO so our `__init__` runs
    first and reaches `super().__init__(...)` to let Django build the
    fields dict, then decorates the widgets.
    """

    def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        super().__init__(*args, **kwargs)
        for _name, field in self.fields.items():
            widget = field.widget
            existing = widget.attrs.get("class", "")
            if isinstance(widget, (forms.CheckboxInput, forms.CheckboxSelectMultiple)):
                css = "form-check-input"
            elif isinstance(widget, forms.Select):
                css = "form-control selectpicker"
                widget.attrs.setdefault("data-live-search", "true")
            else:
                # Text, Textarea, Number, Email, Date, File, etc.
                css = "form-control"
            widget.attrs["class"] = (existing + " " + css).strip()

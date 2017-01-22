import collections
from django import forms
from django.core.exceptions import ValidationError
from regnskab.models import EmailTemplate, Session, config
import tktitler as tk


def placeholder_from_help(cls):
    for f in cls.base_fields.values():
        if f.help_text and 'placeholder' not in f.widget.attrs:
            f.widget.attrs['placeholder'] = f.help_text
            f.help_text = None
    return cls


@placeholder_from_help
class SheetCreateForm(forms.Form):
    start_date = forms.DateField(label='På-dato',
                                 help_text='Format DD.MM.YYYY')
    end_date = forms.DateField(label='Af-dato',
                               help_text='Format DD.MM.YYYY')
    image_file = forms.FileField(label='Scannet PDF',
                                 required=False)
    name = forms.CharField(max_length=200, required=False,
                           label='Særlig krydsliste',
                           help_text='(f.eks. revy)')
    period = forms.IntegerField(label='Bestyrelsesår')
    kinds = forms.CharField(widget=forms.Textarea,
                            label='Priser')

    def clean_kinds(self):
        s = self.cleaned_data['kinds']
        kinds = []
        for line in s.splitlines():
            if not line:
                continue
            try:
                name, unit_price = line.split()
            except ValueError:
                raise ValidationError("Not two words: %r" % line)
            try:
                kinds.append(dict(name=name, unit_price=float(unit_price)))
            except ValueError:
                raise ValidationError("Not a number: %r" % unit_price)
        names = collections.Counter(o['name'] for o in kinds)
        dups = {k: v for k, v in names.items() if v > 1}
        if dups:
            raise ValidationError("Duplicate names: %r" % (dups,))
        return kinds


class EmailTemplateForm(forms.ModelForm):
    class Meta:
        model = EmailTemplate
        fields = ('name', 'subject', 'body', 'format')
        widgets = {'subject': forms.TextInput(attrs={'size': 60})}

    name = forms.CharField(required=True)


class SessionForm(forms.Form):
    subject = forms.CharField(max_length=200,
                              widget=forms.TextInput(attrs={'size': 60}))
    body = forms.CharField(widget=forms.Textarea(attrs={'cols': 70, 'rows': 20}))
    format = forms.ChoiceField(choices=EmailTemplate.FORMAT)


class TransactionBatchForm(forms.Form):
    @tk.set_gfyear(lambda: config.GFYEAR)
    def __init__(self, **kwargs):
        profiles = kwargs.pop('profiles')
        super().__init__(**kwargs)
        self._profiles = []
        for profile, amount, selected in profiles:
            p = 'profile%d_' % profile.id
            if profile.title:
                profile.display_name = (
                    '%s %s' %
                    (tk.prefix(profile.title, type='unicode')
                     if profile.title.period else profile.title.root,
                     profile.name))
            else:
                profile.display_name = profile.name
            self.fields[p + 'selected'] = forms.BooleanField(
                initial=selected,
                required=False, label='%s markeret' % profile.display_name)
            amount_str = '%g' % amount
            try:
                int(amount_str)
            except ValueError:
                amount_str = '%.2f' % amount
            self.fields[p + 'amount'] = forms.FloatField(
                initial=amount_str, label='%s beløb' % profile.display_name,
                widget=forms.TextInput())
            self._profiles.append(profile)

    def profile_fields(self):
        for profile in self._profiles:
            p = 'profile%d_' % profile.id
            yield (profile, self[p + 'amount'], self[p + 'selected'])

    def profile_data(self):
        data = self.cleaned_data
        for profile in self._profiles:
            p = 'profile%d_' % profile.id
            yield (profile, data[p + 'amount'], data[p + 'selected'])


class BalancePrintForm(forms.Form):
    PDF, SOURCE, PRINT = 'pdf', 'source', 'print'
    print_choices = [
        (PDF, 'Hent som PDF'),
        (SOURCE, 'Hent TeX-kildekode'),
        (PRINT, 'Print på A2'),
    ]

    highlight = forms.BooleanField(required=False, initial=True)
    mode = forms.ChoiceField(choices=print_choices, initial='pdf')


@placeholder_from_help
class SheetRowForm(forms.Form):
    start_date = forms.DateField(label='På-dato',
                                 help_text='Format DD.MM.YYYY')
    end_date = forms.DateField(label='Af-dato',
                               help_text='Format DD.MM.YYYY')
    data = forms.CharField(
        widget=forms.HiddenInput(
            attrs=dict(id='tk_rows')))

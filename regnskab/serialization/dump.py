import os
import sys
import decimal
import datetime
import operator
import itertools
import collections

if __name__ == "__main__":
    if os.path.exists('manage.py'):
        BASE_DIR = '.'
    else:
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.append(os.path.join(BASE_DIR, 'venv/lib/python3.6/site-packages'))
    with open(os.path.join(BASE_DIR, 'manage.py')) as fp:
        settings_line = next(l for l in fp
                             if 'DJANGO_SETTINGS_MODULE' in l)
        eval(settings_line.strip())
    import django
    django.setup()


from django.db import models

from regnskab.models import (
    Profile, Title, Alias, SheetStatus,
    Session, Transaction,
    Sheet, PurchaseKind, SheetRow, Purchase,
    EmailTemplate, Email,
    SheetImage,
)


DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'
DATE_FORMAT = '%Y-%m-%d'


def field_dumper(field):
    field_name = field.name

    if isinstance(field, models.DateTimeField):
        def dump_field(self, instance):
            v = getattr(instance, field_name)
            return v and v.strftime(DATETIME_FORMAT)
    elif isinstance(field, models.DateField):
        def dump_field(self, instance):
            v = getattr(instance, field_name)
            return v and v.strftime(DATE_FORMAT)
    elif isinstance(field, models.DecimalField):
        def dump_field(self, instance):
            v = getattr(instance, field_name)
            return v and str(v)
    else:
        if isinstance(field, models.ForeignKey):
            field_name += '_id'

        def dump_field(self, instance):
            return getattr(instance, field_name)

    return dump_field


def field_loader(field):
    field_name = field.name

    if isinstance(field, models.DateTimeField):
        def load_field(self, data, instance):
            v = data[field_name]
            setattr(instance, field_name,
                    v and datetime.datetime.strptime(v, DATETIME_FORMAT))
    elif isinstance(field, models.DateTimeField):
        def load_field(self, data, instance):
            v = data[field_name]
            setattr(instance, field_name,
                    v and datetime.datetime.strptime(v, DATE_FORMAT).date())
    elif isinstance(field, models.DecimalField):
        def load_field(self, data, instance):
            v = data[field_name]
            setattr(instance, field_name, v and decimal.Decimal(v))
    else:
        if isinstance(field, models.ForeignKey):
            field_name += '_id'

        def load_field(self, data, instance):
            setattr(instance, field_name, data[field_name])

    return load_field


def model_dumper(model):
    def dump_model(self):
        by_parent = {}
        try:
            parent_field = self.parent_field
        except AttributeError:
            parent_fn = lambda instance: None  # noqa
            result = by_parent[None] = []
        else:
            parent_fn = operator.attrgetter(parent_field + '_id')
            result = by_parent

        children = {}
        try:
            child_fields = self.children
        except AttributeError:
            pass
        else:
            for child_name, child_type in child_fields.items():
                try:
                    child_dump_fn = getattr(self, 'dump_' + child_name)
                except AttributeError:
                    child_dump_fn = child_type().dump
                child_dump = child_dump_fn()
                assert isinstance(child_dump, dict)
                for parent, data in child_dump.items():
                    if data is not self.OMIT:
                        children.setdefault(parent, {})[child_name] = data

        field_names = self._fields()
        for instance in self.get_queryset():
            instance_data = {}
            for field_name in field_names:
                dump_method = getattr(self, 'dump_' + field_name)
                dumped_value = dump_method(instance)
                if dumped_value is not self.OMIT:
                    instance_data[field_name] = dumped_value
            instance_data.update(children.get(instance.pk, {}))
            by_parent.setdefault(parent_fn(instance), []).append(instance_data)
        return result

    return dump_model


def model_loader(model):
    def load_model(self, data):
        instance = model()
        for field_name in self._fields():
            getattr(self, 'load_' + field_name)(data, instance)
        return instance

    return load_model


class Data:
    OMIT = object()

    def _fields(self):
        try:
            return self._fields_cache
        except AttributeError:
            pass
        try:
            self._fields_cache = self.fields
            return self._fields_cache
        except AttributeError:
            pass
        try:
            exclude = set(self.exclude)
        except AttributeError:
            exclude = set()
        method_order = []
        dump_methods = set()
        load_methods = set()
        for k in dir(self):
            if k.startswith('dump_'):
                dump_methods.add(k[5:])
                if k[5:] not in exclude:
                    method_order.append(k[5:])
            elif k.startswith('load_'):
                load_methods.add(k[5:])
        diff = (dump_methods - exclude) ^ (load_methods - exclude)
        if diff:
            raise TypeError(diff)
        explicit_fields = getattr(self, 'fields', ())
        self._fields_cache = list(explicit_fields) + method_order
        return self._fields_cache


def base(model):
    members = {}
    for field in model._meta.fields:
        members['dump_' + field.name] = field_dumper(field)
        members['load_' + field.name] = field_loader(field)
    members['dump'] = model_dumper(model)
    members['load'] = model_loader(model)
    members['get_queryset'] = lambda self: model.objects.all()
    return type(model.__name__, (Data,), members)


class TitleData(base(Title)):
    parent_field = 'profile'
    fields = ('root', 'period', 'kind')


class AliasData(base(Alias)):
    parent_field = 'profile'
    fields = ('root', 'period', 'is_title',
              'start_time', 'end_time',
              'created_time')


class SheetStatusData(base(SheetStatus)):
    parent_field = 'profile'
    fields = ('start_time', 'end_time',
              'created_time')


class ProfileData(base(Profile)):
    fields = ('id', 'name', 'email')
    children = {
        'titles': TitleData,
        'aliases': AliasData,
        'statuses': SheetStatusData,
    }


class EmailData(base(Email)):
    parent_field = 'session'
    fields = ('profile', 'subject', 'body',
              'recipient_name', 'recipient_email')


class EmailTemplateData(base(EmailTemplate)):
    fields = ('name', 'subject', 'body', 'format', 'created_time')


class SheetKindRelationData(base(PurchaseKind.sheets.through)):
    fields = ('sheet_id', 'purchasekind_id')


class PurchaseKindData(base(PurchaseKind)):
    fields = ('id', 'position', 'name', 'unit_price')


class PurchaseData(base(Purchase)):
    parent_field = 'row'
    fields = ('kind', 'count')


class SheetRowData(base(SheetRow)):
    parent_field = 'sheet'
    fields = ('position', 'name', 'profile')
    exclude = ('image_start', 'image_stop')
    children = {
        'purchases': PurchaseData,
    }


class SheetData(base(Sheet)):
    parent_field = 'session'
    fields = ('id', 'name', 'start_date', 'end_date', 'period', 'created_time')
    children = {
        'rows': SheetRowData,
    }

    def get_queryset(self):
        return super().get_queryset().exclude(session=None)


class SessionData(base(Session)):
    fields = ('email_template', 'period', 'send_time', 'created_time')
    children = {
        'emails': EmailData,
        'sheets': SheetData,
    }


class LegacySheetRowData(base(SheetRow)):
    parent_field = 'sheet'
    fields = ('profile',)
    exclude = ('name', 'position','image_start', 'image_stop')
    children = {
        'purchases': PurchaseData,
    }

    def load(self, iterable):
        dump_lists = list(iterable)
        for dump_list in dump_lists:
            res = []
            for i, o in enumerate(dump_list):
                res.append(SheetRow(
                    profile_id=o['profile'],
                    purcha


class LegacySheetData(base(Sheet)):
    fields = ('id', 'name', 'start_date', 'end_date', 'period', 'created_time')
    children = {
        'rows': LegacySheetRowData,
    }

    def get_queryset(self):
        return super().get_queryset().filter(session=None)


class LegacyTransactionData(base(Transaction)):
    fields = ('kind', 'profile', 'time', 'period', 'amount', 'note',
              'created_time')

    def get_queryset(self):
        return super().get_queryset().filter(session=None)


class RegnskabData:
    attributes = {
        'profiles': ProfileData,
        'sessions': SessionData,
        'old_sheets': LegacySheetData,
        'old_transactions': LegacyTransactionData,
    }

    def dump(self):
        return {k: v().dump() for k, v in self.attributes.items()}

    def load(self):
        return {k: v().load() for k, v in self.attributes.items()}


def main():
    from pprint import pprint
    pprint(RegnskabData().dump(), width=200)


if __name__ == '__main__':
    main()

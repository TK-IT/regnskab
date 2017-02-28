import os
import sys
import operator

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

from regnskab.models import (
    Profile, Title, Alias, SheetStatus,
    Session, Transaction,
    Sheet, PurchaseKind, SheetRow, Purchase,
    EmailTemplate, Email,
    SheetImage,
)


def field_dumper(field):
    field_name = field.name

    def dump_field(self, instance):
        return getattr(instance, field_name)

    return dump_field


def field_loader(field):
    field_name = field.name

    def load_field(self, data, instance):
        setattr(instance, field_name, data[field_name])

    return load_field


def model_dumper(model):
    def dump_model(self):
        by_parent = {}
        try:
            parent_field = self.parent_field
        except AttributeError:
            parent_fn = lambda instance: None
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
                child_type_instance = child_type()
                child_dump = child_type_instance.dump()
                assert isinstance(child_dump, dict)
                for parent, data in child_dump.items():
                    children.setdefault(parent, {})[child_name] = data

        field_names = self._fields()
        for instance in self.get_queryset():
            instance_data = {
                field_name: getattr(self, 'dump_' + field_name)(instance)
                for field_name in field_names}
            instance_data.update(children.get(instance.pk, {}))
            by_parent.setdefault(parent_fn(instance), []).append(instance_data)
        return result

    return dump_model


def model_loader(model):
    def load_model(self, data):
        instance = model()
        for field_name in self._fields():
            getattr(self, 'load_' + field_name)(data, instance)
        return model(**kwargs)

    return load_model


class Data:
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
        dump_methods = set()
        load_methods = set()
        for k in dir(self):
            if k.startswith('dump_'):
                dump_methods.add(k[5:])
            elif k.startswith('load_'):
                load_methods.add(k[5:])
        diff = (dump_methods - exclude) ^ (load_methods - exclude)
        if diff:
            raise TypeError(diff)
        self._fields_cache = sorted(dump_methods - exclude)
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
    fields = ('name', 'email')
    children = {
        'titles': TitleData,
        'aliases': AliasData,
        'statuses': SheetStatusData,
    }


def main():
    from pprint import pprint
    pprint(ProfileData().dump())


if __name__ == '__main__':
    main()

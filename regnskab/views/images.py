import io
import logging
import tempfile

from django.views.generic import (
    CreateView, UpdateView, DetailView, FormView,
)
from django.views.generic.detail import (
    BaseDetailView, SingleObjectMixin,
)
from django.views.generic.edit import FormMixin
from django.shortcuts import redirect, get_object_or_404
from django.http import HttpResponse

from regnskab.models import SheetImageStack, SheetImage
from .auth import regnskab_permission_required_method
from regnskab.images.utils import imagemagick_page_count
from regnskab.images.extract import (
    extract_quad, extract_rows_cols, extract_crosses,
)
from regnskab.images.forms import SheetImageForm

import PIL


logger = logging.getLogger('regnskab')


class SheetImageStackCreate(CreateView):
    model = SheetImageStack
    fields = ('file',)
    template_name = 'regnskab/sheet_image_stack_create.html'

    @regnskab_permission_required_method
    def dispatch(self, request, *args, **kwargs):
        self.regnskab_session = get_object_or_404(
            Session.objects, pk=kwargs['session'])
        if not self.regnskab_session or self.regnskab_session.sent:
            return already_sent_view(request, self.regnskab_session)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        f = form.cleaned_data['file']
        with tempfile.NamedTemporaryFile('r+b') as fp:
            f.open('rb')
            fp.write(f.read())
            fp.flush()
            try:
                sheets = imagemagick_page_count(fp.name)
            except Exception as exn:
                form.add_error(None, str(exn))
                return self.form_invalid(form)
        object = form.save(commit=False)
        object.sheets = sheets
        object.session = self.regnskab_session
        object.save()
        return redirect('regnskab:sheet_image_stack_export',
                        pk=object.pk)


class SheetImageStackExport(FormView):
    form_class = SheetCreateForm

    @regnskab_permission_required_method
    def dispatch(self, request, *args, **kwargs):
        self.regnskab_session = get_object_or_404(
            Session.objects, pk=kwargs['session'])
        if not self.regnskab_session or self.regnskab_session.sent:
            return already_sent_view(request, self.regnskab_session)
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        kinds = get_default_prices()
        return dict(kinds='\n'.join('%s %s' % x for x in kinds),
                    period=config.GFYEAR)

    def form_valid(self, form):
        data = form.cleaned_data
        s = Sheet(name=data['name'],
                  start_date=data['start_date'],
                  end_date=data['end_date'],
                  period=data['period'],
                  created_by=self.request.user,
                  session=self.regnskab_session)
        s.save()
        for i, kind in enumerate(data['kinds']):
            s.purchasekind_set.create(
                name=kind['name'],
                position=i + 1,
                unit_price=kind['unit_price'])
        logger.info("%s: Opret ny krydsliste id=%s i opgørelse=%s " +
                    "med priser %s",
                    self.request.user, s.pk, self.regnskab_session.pk,
                    ' '.join('%s=%s' % (k['name'], k['unit_price'])
                             for k in data['kinds']))
        return redirect('regnskab:sheet_update', pk=s.pk)


class SheetImageCreate(CreateView):
    model = SheetImage
    fields = ('stack', 'sheet')
    template_name = 'regnskab/sheet_image_create.html'

    @regnskab_permission_required_method
    def dispatch(self, request, *args, **kwargs):
        self.regnskab_session = get_object_or_404(
            Session.objects, pk=kwargs['session'])
        if not self.regnskab_session or self.regnskab_session.sent:
            return already_sent_view(request, self.regnskab_session)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        object = form.save(commit=False)
        if not 1 <= object.sheet <= object.stack.sheets:
            form.add_error('sheet',
                           'Angiv et tal mellem 1 og %s.' %
                           object.stack.sheets)
            return self.form_invalid(form)
        extract_quad(object)
        extract_rows_cols(object)
        extract_crosses(object)
        object.save()
        return redirect('regnskab:sheet_image_update', pk=object.pk)


class SheetImageFile(BaseDetailView):
    model = SheetImage

    @regnskab_permission_required_method
    def dispatch(self, request, *args, **kwargs):
        self.regnskab_session = get_object_or_404(
            Session.objects, pk=kwargs['session'])
        return super().dispatch(request, *args, **kwargs)

    def render_to_response(self, context):
        img = PIL.Image.fromarray(self.object.get_image())
        output = io.BytesIO()
        img.save(output, 'PNG')
        return HttpResponse(
            content=output.getvalue(),
            content_type='image/png')


class SheetImageUpdate(FormView):
    form_class = SheetImageForm
    template_name = 'regnskab/sheet_image_update.html'

    @regnskab_permission_required_method
    def dispatch(self, request, *args, **kwargs):
        self.regnskab_session = get_object_or_404(
            Session.objects, pk=kwargs['session'])
        if not self.regnskab_session or self.regnskab_session.sent:
            return already_sent_view(request, self.regnskab_session)
        return super().dispatch(request, *args, **kwargs)

    def get_object(self):
        return get_object_or_404(SheetImage.objects, pk=self.kwargs['pk'])

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        context_data['object'] = self.get_object()
        return context_data

    def get_form_kwargs(self, **kwargs):
        r = super().get_form_kwargs(**kwargs)
        r['instance'] = self.get_object()
        return r

    def form_valid(self, form):
        o = self.get_object()
        o.crosses = form.get_crosses()
        o.compute_person_counts()
        o.save()
        return  # TODO

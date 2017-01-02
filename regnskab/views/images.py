import io
import base64
import logging
import tempfile
import collections

from django.views.generic import (
    CreateView, UpdateView, DetailView, FormView, View,
)
from django.views.generic.detail import (
    BaseDetailView, SingleObjectMixin,
)
from django.views.generic.edit import FormMixin
from django.shortcuts import redirect, get_object_or_404
from django.http import HttpResponse

from regnskab.models import Sheet, SheetImage
from .auth import regnskab_permission_required_method
from regnskab.images.forms import SheetImageForm

import PIL


logger = logging.getLogger('regnskab')


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


class Svm(View):
    def get(self, request):
        from regnskab.images.extract import get_crosses_from_counts

        pos = []
        neg = []
        for o in SheetImage.objects.all()[0:4]:
            imgs, coords = get_crosses_from_counts(o)
            c = collections.Counter(coords)
            dup = {k: v for k, v in c.items() if v > 1}
            assert not dup, dup
            coords = frozenset(coords)
            for i, row in enumerate(imgs):
                for j, img in enumerate(row):
                    if (i, j) in coords:
                        pos.append(img.ravel())
                    else:
                        neg.append(img.ravel())

        from sklearn.svm import SVC

        svm = SVC(C=1e3, kernel='linear')
        svm.fit(pos + neg, [1] * len(pos) + [0] * len(neg))

        from regnskab.images.utils import save_png

        def img_tag(im_data):
            png_data = save_png(im_data.reshape((24, 24, 3)))
            png_b64 = base64.b64encode(png_data).decode()
            return '<img src="data:image/png;base64,%s" />' % png_b64

        result = []

        sv_labels = svm.predict(svm.support_vectors_)
        for i, (img, label) in enumerate(zip(svm.support_vectors_, sv_labels)):
            if label == 0:
                result.append(img_tag(img))
        result.append('<hr />')
        for i, (img, label) in enumerate(zip(svm.support_vectors_, sv_labels)):
            if label == 1:
                result.append(img_tag(img))

        result.append('<hr />')

        for i, label in enumerate(svm.predict(pos)):
            assert label in (0, 1), label
            if label == 0:
                result.append(img_tag(pos[i]))

        result.append('<hr />')

        for i, label in enumerate(svm.predict(neg)):
            assert label in (0, 1), label
            if label == 1:
                result.append(img_tag(neg[i]))

        return HttpResponse(''.join(result))

from django.views.generic import TemplateView
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseServerError
import simplejson as json

from django.template.loader import get_template
from django.template import Context
from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator


class BaseView(TemplateView):

    login_exempt = True
    csrf_exempt = True

    def dispatch(self, request, *args, **kwargs):

        return TemplateView.dispatch(self, request, *args, **kwargs)

    def redirect(self, url):

        return HttpResponseRedirect(url)

    def response(self, response):

        return HttpResponse(response)

    def response_error(self, response):

        return HttpResponseServerError(response)

    def json_response(self, response):

        return self.response(json.dumps(response))

    def render(self, template, context):

        return get_template(template).render(Context(context))

    def get_list_args(self, startswith):

        return [key[len(startswith):] for key, value in self.request.POST.iteritems() if key.startswith(startswith)]

    def get_params(self, data, params):

        dict_params = {}
        for param in params:
            dict_params[param] = data.get(param)
        return dict_params


class AjaxBaseView(BaseView):

    def on_success(self):

        return self.json_response({"status": "ok"})

    def on_fail(self, error):

        return self.json_response({"status": "fail", "error": error})


class AjaxSaveBaseView(AjaxBaseView):

    def after_save(self, entity):

        pass

    def post(self, *args, **kwargs):

        try:
            entity = self.service.save(self.request)
            self.after_save(entity)
            return self.render(self.on_success)

        except ValidationError, e:
            return self.render(self.on_fail, str(e))

    def render(self, function, *args, **kwargs):

        return self.response(function(*args, **kwargs))


class AjaxFormSaveBaseView(AjaxSaveBaseView):

    def get_data(self, request):

        return request.POST

    def post(self, *args, **kwargs):

        form = self.form(self.get_data(self.request), *args, **kwargs)

        if (form.is_valid()):
            form.save()
            return self.render(self.on_success)

        return self.render(self.on_error, **form.errors)

    def on_error(self, **data):

        return self.json_response(data)


class CachedView(BaseView):

    @method_decorator(cache_page(60 * 60))
    def dispatch(self, request, *args, **kwargs):
        return super(BaseView, self).dispatch(request, *args, **kwargs)


class ValidationError(Exception):

    pass

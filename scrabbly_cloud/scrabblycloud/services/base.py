# -*- coding: utf-8 -*-
from django.template.loader import get_template
from django.template import Context
from django.shortcuts import get_object_or_404

from django.db.models import Q
from django.template.loader import render_to_string
from django.http import HttpResponse
from django.utils.cache import add_never_cache_headers
from django.utils import simplejson

class BaseService(object):

    _repo = property(fget=lambda self: self.entity.objects)
    _page_size = 10

    default_query_params = {}

    def __getattr__(self, name):
        """
            Delegates automatically all undefined methods on the repository.
            The entity property must be overridden in all subclasses.
        """

        def decorator(*args, **kwargs):

            method = getattr(self._repo, name)
            if method is None:
                raise AttributeError("'%s' has no attribute '%s'" % (self.__class__.__name__, name))

            for key, value in self.default_query_params.iteritems():
                kwargs.setdefault(key, value)

            return method(*args, **kwargs)

        return decorator

    def get_page(self, page=0, size=None, min_page=None, **kwargs):

        if size is None:
            size = self._page_size

        page = int(page)

        if min_page is not None:
            min_page = int(min_page)
            limit = (page + 1) * size
            offset = min_page * size
        else:
            limit = (page + 1) * size
            offset = size * page

        return self._get_objects(self._get_page_query(offset, limit, **kwargs))

    def _get_page_query(self, offset, limit, **kwargs):

        return self.all()[offset:limit]

    def list(self, start, size, **kwargs):
        page = int(start / size)
        return self.get_page(page=page, size=size, min_page=None, **kwargs)

    def _get_objects(self, objects):
        """ Override to add behaviour """

        return objects

    def get_one(self, **kwargs):

        objects = self.filter(**kwargs)
        return objects[0] if objects else None

    def new(self, **kwargs):

        return self.entity(**kwargs)

    def _get_or_new(self, **kwargs):

        try:
            obj, created = self.get_or_create(**kwargs)
        except:
            obj, created = self.entity(**kwargs), True
        return obj, created

    def get_or_new(self, **kwargs):

        obj, _ = self._get_or_new(**kwargs)
        return obj

    def get_or_new_created(self, **kwargs):

        return self._get_or_new(**kwargs)

    def get_form(self):

        return None

    def _get_data(self, request):

        data = dict([(key, value) for key, value in request.POST.iteritems() if key != "csrfmiddlewaretoken"])
        data.update(self._get_additional_data(request))
        return data

    def _get_additional_data(self, request):

        return {}

    def _get_entity(self, request):

        return self.get_or_new(**self._get_data(request))

    def _set_data(self, entity, request):

        return entity

    def save(self, request):

        entity = self._get_entity(request)

        self._set_data(entity, request)
        entity.save()
        self._post_save(entity, request)

        return entity

    def _post_save(self, entity, request):

        pass

    def render(self, template, context):

        context = Context(context)
        return get_template(template).render(context)

    def get_object_or_404(self, **kwargs):

        return get_object_or_404(self.entity, **kwargs)

    def delete(self, *args, **kwargs):

        logical_delete = kwargs.pop("logical", False)

        objs = self.filter(*args, **kwargs)
        for obj in objs:
            if not logical_delete:
                obj.delete()
            else:
                obj.active = False
                obj.save()

    def get_params(self, data, params):

        dict_params = {}
        for param in params:
            dict_params[param] = data.get(param)
        return dict_params

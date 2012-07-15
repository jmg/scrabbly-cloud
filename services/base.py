
class BaseService(object):

    def __getattr__(self, name):

        def decorator(*args, **kwargs):

            return getattr(self.entity.query, name)(*args, **kwargs)

        return decorator

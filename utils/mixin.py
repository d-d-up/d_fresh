from django.contrib.auth.decorators import login_required
from django.views.generic import View


class LoginRequiredView(View):
    @classmethod
    def as_view(cls, **initkwargs):
        view = super(LoginRequiredView, cls).as_view(**initkwargs)
        return login_required(view)


class LoginRequiredMixin(object):
    @classmethod
    def as_view(cls, **initkwargs):
        # UserInfoView父类中的as_view
        view = super(LoginRequiredMixin, cls).as_view(**initkwargs)
        return login_required(view)
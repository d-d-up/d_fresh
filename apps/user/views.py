from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse
from django.core.paginator import Paginator
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponse
from django.conf import settings
from django.core.mail import send_mail
from django.views.generic import View

from user.models import User, Address
from goods.models import GoodsSKU
from order.models import OrderInfo,OrderGoods

from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from itsdangerous import SignatureExpired
from celery_tasks.tasks import send_register_active_email
from utils.mixin import LoginRequiredMixin
from django_redis import get_redis_connection
import re
# Create your views here.


# /user/register
def register(request):
    '''注册'''
    if request.method == 'GET':
        # 显示注册页面
        return render(request, 'register.html')
    else:
        # 进行注册处理
        # 接收参数
        username = request.POST.get('user_name')
        password = request.POST.get('pwd')
        email = request.POST.get('email')
        allow = request.POST.get('allow')

        # 校验参数
        # 校验参数的完整性
        if not all([username, password, email]):
            return render(request, 'register.html', {'errmsg': '参数不完整'})

        # 校验是否同意协议
        if allow != 'on':
            return render(request, 'register.html', {'errmsg': '请同意协议'})

        # 校验邮箱是否合法
        if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return render(request, 'register.html', {'errmsg': '邮箱格式不正确'})

        # 校验用户名是否存在
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            # 用户名不存在
            user = None

        if user:
            # 用户名已存在
            return render(request, 'register.html', {'errmsg': '用户名已存在'})

        # 进行业务处理: 进行注册
        user = User.objects.create_user(username, email, password)
        user.is_active = 0
        user.save()

        # 返回应答: 跳转到首页
        return redirect(reverse('goods:index'))


# /user/register_handle
def register_handle(request):
    '''注册处理'''
    # 接收参数
    username = request.POST.get('user_name')
    password = request.POST.get('pwd')
    email = request.POST.get('email')
    allow = request.POST.get('allow')

    # 校验参数
    # 校验参数的完整性
    if not all([username, password, email]):
        return render(request, 'register.html', {'errmsg':'参数不完整'})

    # 校验是否同意协议
    if allow != 'on':
        return render(request, 'register.html', {'errmsg': '请同意协议'})

    # 校验邮箱是否合法
    if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
        return render(request, 'register.html', {'errmsg': '邮箱格式不正确'})

    # 校验用户名是否存在
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        # 用户名不存在
        user = None

    if user:
        # 用户名已存在
        return render(request, 'register.html', {'errmsg': '用户名已存在'})

    # 进行业务处理: 进行注册
    user = User.objects.create_user(username, email, password)
    user.is_active = 0
    user.save()

    # 返回应答: 跳转到首页
    return redirect(reverse('goods:index'))


# /user/register
class RegisterView(View):
    '''注册'''
    def get(self, request):
        '''显示'''
        return render(request, 'register.html')

    def post(self, request):
        '''注册处理'''
        # 接收参数
        username = request.POST.get('user_name')
        password = request.POST.get('pwd')
        email = request.POST.get('email')
        allow = request.POST.get('allow')

        # 校验参数
        # 校验参数的完整性
        if not all([username, password, email]):
            return render(request, 'register.html', {'errmsg': '参数不完整'})

        # 校验是否同意协议
        if allow != 'on':
            return render(request, 'register.html', {'errmsg': '请同意协议'})

        # 校验邮箱是否合法
        if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return render(request, 'register.html', {'errmsg': '邮箱格式不正确'})

        # 校验用户名是否存在
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            # 用户名不存在
            user = None

        if user:
            # 用户名已存在
            return render(request, 'register.html', {'errmsg': '用户名已存在'})

        # 进行业务处理: 进行注册
        user = User.objects.create_user(username, email, password)
        user.is_active = 0
        user.save()

        # 加密用户的身份信息，生成激活token itsdangerous
        serializer = Serializer(settings.SECRET_KEY, 3600)
        info = {'confirm':user.id}
        token = serializer.dumps(info) # bytes
        token = token.decode() # str

        # 发送激活邮件,邮件中需要有激活链接，需要在激活链接中包含用户的身份信息 /user/active/1
        # 激活链接格式: /user/active/用户身份加密后的信息 /user/active/token
        # 找其他人帮助我们发送邮件 celery:异步执行任务
        # 发出任务 send_mail
        send_register_active_email.delay(email, username, token)

        # 返回应答: 跳转到首页
        # return redirect(reverse('goods:index'))


# /user/active/加密信息token
class ActiveView(View):
    '''激活'''
    def get(self, request, token):
        '''激活'''
        serializer = Serializer(settings.SECRET_KEY, 3600)
        try:
            info = serializer.loads(token)
            # 获取待激活用户的id
            user_id = info['confirm']

            # 获取用户信息
            user = User.objects.get(id=user_id)
            user.is_active = 1
            user.save()

            # 跳转到登录页面
            return redirect(reverse('user:login'))
        except SignatureExpired:
            # 激活链接已失效
            return HttpResponse('激活链接已失效')


# /user/login
class LoginView(View):
    '''登录'''
    def get(self, request):
        '''显示'''
        # 尝试从cookie中获取username
        if 'username' in request.COOKIES:
            # 记住了用户名
            username = request.COOKIES['username']
            checked = 'checked'
        else:
            # 没记住用户名
            username = ''
            checked = ''

        # 使用模板
        return render(request, 'login.html', {'username':username, 'checked':checked})

    def post(self, request):
        '''登录校验'''
        # 接收参数
        username = request.POST.get('username')
        password = request.POST.get('pwd')
        remember = request.POST.get('remember') # on

        # 参数校验
        if not all([username, password]):
            return render(request, 'login.html', {'errmsg':'参数不完整'})

        # 业务处理: 登录校验
        user = authenticate(username=username, password=password)
        if user is not None:
            # 用户名密码正确
            if user.is_active:
                # 用户已激活
                # 记录用户的登录状态
                login(request, user)

                # 获取登录后跳转的地址, 默认跳转到首页
                next_url = request.GET.get('next', reverse('goods:index')) # None

                # 判断是否需要记住用户名
                response = redirect(next_url)
                # 设置cookie, 需要通过HttpReponse类的实例对象, set_cookie
                # HttpResponseRedirect JsonResponse
                if remember == 'on':
                    # 需要记住用户名
                    response.set_cookie('username', username, max_age=7*24*3600)
                else:
                    # 不需要记住用户名
                    response.delete_cookie('username')

                # 跳转到首页
                return response
            else:
                # 用户未激活
                return render(request, 'login.html', {'errmsg':'账户未激活'})
        else:
            # 用户名或密码错误
            return render(request, 'login.html', {'errmsg': '用户名或密码错误'})


# /user/logout
class LogoutView(View):
    '''退出登录'''
    def get(self, request):
        # 清除用户的登录信息
        logout(request)

        # 跳转到首页
        return redirect(reverse('goods:index'))

# django框架会给request对象增加一个属性user, request.user
# 如果用户已经登录，user就是认证模型类的对象：User类的实例对象
# 如果用户没有登录，user是AnonymousUser类的实例对象
# 不管是哪一个类的实例对象，user有一个方法is_authenticated
# 在模板文件中可以直接使用user对象，django框架会把request.user对象作为模板上下文传递给模板文件

from utils.mixin import LoginRequiredView


# /user/
# class UserInfoView(View):
# class UserInfoView(LoginRequiredView):
class UserInfoView(LoginRequiredMixin, View):
    '''用户中心-信息页'''
    def get(self, request):
        '''显示'''
        # 获取登录的用户
        user = request.user
        # 获取用户的默认地址
        address = Address.objects.get_default_address(user)

        # 获取用户的历史浏览记录
        # from redis import StrictRedis
        # conn = StrictRedis(host='172.16.179.142:6379',db=10)
        conn = get_redis_connection('default')
        history_key = 'history_%d'%user.id

        # 获取用户最新浏览的5个商品id lrange history 0 4
        sku_ids = conn.lrange(history_key, 0, 4) # ['2', '1', '3']

        # 获取用户浏览的商品的信息

        # skus_li = []
        # skus = GoodsSKU.objects.filter(id__in=sku_ids)
        #
        # for sku_id in sku_ids:
        #     # 遍历商品的信息
        #     for sku in skus:
        #         if sku.id == int(sku_id):
        #             skus_li.append(sku)

        skus = []
        for sku_id in sku_ids:
            # 根据sku_id获取商品的信息
            sku = GoodsSKU.objects.get(id=sku_id)
            # 追加到列表中
            skus.append(sku)

        # 组织模板上下文
        context = {'skus':skus,'address':address, 'page':'user'}

        # 使用模板
        return render(request, 'user_center_info.html', context)


# /user/order/页码
class UserOrderView(LoginRequiredMixin, View):
    '''用户中心-订单页'''
    def get(self, request, page):
        '''显示'''
        # 获取登录用户
        user = request.user
        # 获取用户的订单信息
        orders = OrderInfo.objects.filter(user=user).order_by('-create_time')

        # 遍历orders，获取每个订单的订单商品的信息
        for order in orders:
            # 查询和order相关的订单商品的信息
            order_skus = OrderGoods.objects.filter(order=order)
            # 遍历order_skus, 计算订单中每个商品的小计
            for order_sku in order_skus:
                # 计算小计
                amount = order_sku.count*order_sku.price
                # 给order_sku增加属性amount,保存订单商品的小计
                order_sku.amount = amount
            # 计算订单的实付款
            total_amount = order.total_price + order.transit_price
            # 获取订单状态的名称
            status_name = OrderInfo.ORDER_STATUS[order.order_status]
            # 给order增加属性order_skus, 保存订单商品的信息
            order.order_skus = order_skus
            order.total_amount = total_amount
            order.status_name = status_name

        # 分页
        paginator = Paginator(orders, 1)

        # 处理页码
        page = int(page)

        if page <= 0 or page > paginator.num_pages:
            # 默认获取第1页的内容
            page = 1

        # 获取第page页的Page对象
        order_page = paginator.page(page)

        # 处理页码列表
        # 1.总页数<5, 显示所有页码
        # 2.当前页是前3页，显示1-5页
        # 3.当前页是后3页，显示后5页
        # 4.其他情况，显示当前页的前2页，当前页，当前页的后2页
        num_pages = paginator.num_pages
        if num_pages < 5:
            pages = range(1, num_pages + 1)
        elif page <= 3:
            pages = range(1, 6)
        elif num_pages - page <= 2:
            pages = range(num_pages - 4, num_pages + 1)
        else:
            pages = range(page - 2, page + 3)

        # 组织上下文数据
        context = {'order_page':order_page,
                   'pages':pages,
                   'page': 'order'}

        # 使用模板
        return render(request, 'user_center_order.html', context)


# 模型管理器类
# /user/address
class AddressView(LoginRequiredMixin, View):
    '''用户中心-地址页'''
    def get(self, request):
        '''显示'''
        # 获取登录的user对象
        user = request.user
        # 如果用户存在默认地址，新添加的地址不作为默认地址，否则作为默认地址
        address = Address.objects.get_default_address(user)

        # 使用模板
        return render(request, 'user_center_site.html', {'address':address, 'page':'address'})

    def post(self, request):
        '''地址添加'''
        # 接收参数
        receiver = request.POST.get('receiver')
        addr = request.POST.get('addr')
        zip_code = request.POST.get('zip_code')
        phone = request.POST.get('phone')
        print()
        # 参数校验
        if not all([receiver, addr, phone]):
            return render(request, 'user_center_site.html', {'errmsg':'参数不完整'})

        # 业务处理: 添加收货地址
        # 获取登录的user对象
        user = request.user
        # 如果用户存在默认地址，新添加的地址不作为默认地址，否则作为默认地址
        address = Address.objects.get_default_address(user)

        if address:
            # 存在默认地址
            is_default = False
        else:
            # 不存在默认地址
            is_default = True

        # 添加地址
        Address.objects.create(user=user,
                               receiver=receiver,
                               addr=addr,
                               zip_code=zip_code,
                               phone=phone,
                               is_default=is_default)

        # 返回应答：刷新地址页面
        return redirect(reverse('user:address'))
















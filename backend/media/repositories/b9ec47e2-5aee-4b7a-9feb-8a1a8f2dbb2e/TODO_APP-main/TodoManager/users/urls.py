from django.urls import include, path
from users import views as user_views
from django.contrib.auth import views as auth_views
urlpatterns = [
    path("register/", user_views.register, name="register"),
    path("login/", auth_views.LoginView.as_view(template_name="login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(template_name="logout.html", next_page="homepage", http_method_names=['get', 'post']), name="logout"),
    
]

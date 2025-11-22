"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path

import main.views as main_views
import scraper.views as scraper_views
import training.views as training_views
import selection.views as selection_views
import chat.views as chat_views

urlpatterns = [
    path('admin/', admin.site.urls),

    path('', main_views.home, name='home'),
    path('about/', main_views.about, name='about'),
    path('contact/', main_views.contact, name='contact'),

    path('scrape/', scraper_views.scrape_character, name='scrape_character'),
    path("train/", training_views.train_model, name="train_model"),
    path('character_select/', selection_views.character_select, name='character_select'),
    path('delete-character/<str:name>/', selection_views.delete_character, name='delete_character'),

    path('<int:model_id>/start/', chat_views.start_chat, name='start_chat'),
    path('session/<int:session_id>/', chat_views.chat_window, name='chat_window'),
    path('session/<int:session_id>/send/', chat_views.send_message, name='send_message'),
    path('session/<int:session_id>/clear/', chat_views.clear_chat, name='clear_chat'),

    path("openai/webhook/", training_views.openai_webhook, name="openai_webhook"),
]

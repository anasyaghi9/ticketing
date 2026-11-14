from django.contrib import admin

from .models import Booking, Event, Seat

admin.site.register(Event)
admin.site.register(Seat)
admin.site.register(Booking)
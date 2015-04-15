from __future__ import unicode_literals
from rest_framework import viewsets, filters
from rest_framework.filters import DjangoFilterBackend
import django_filters
from libreosteoweb import models 
from rest_framework.decorators import action, detail_route, list_route
from libreosteoweb.api import serializers as apiserializers
from rest_framework.response import Response
from haystack.query import SearchQuerySet
from django.core import serializers
from django.http import HttpResponse
from django.views.generic import View
from haystack.utils import Highlighter
from haystack.views import SearchView
import json
import logging
from django.contrib.auth.models import User
from .permissions import IsStaffOrTargetUser, TargetUserSettingsPermissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from datetime import date, datetime
from rest_framework import status
from django.views.generic.base import TemplateView
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import (REDIRECT_FIELD_NAME, get_user_model )
from django.template.response import TemplateResponse
from django.utils.http import is_safe_url
from django.shortcuts import resolve_url
from django.conf import settings
from django.http import HttpResponseRedirect


# Get an instance of a logger
logger = logging.getLogger(__name__)

def create_superuser(request, user):
    UserModel = get_user_model()
    UserModel.objects.create_superuser(user['username'], '', user['password1'])

@csrf_protect
@never_cache
def create_admin_account(request, template_name='account/create_admin_account.html',
    redirect_field_name=REDIRECT_FIELD_NAME,
    registration_form=UserCreationForm):
    """
    Displays the login form and handles the login action.
    """
    redirect_to = request.POST.get(redirect_field_name,
    request.GET.get(redirect_field_name, ''))
    if request.method == "POST":
        form = registration_form(request.POST)
        if form.is_valid():
            # Ensure the user-originating redirection url is safe.
            if not is_safe_url(url=redirect_to, host=request.get_host()):
                redirect_to = resolve_url(settings.LOGIN_REDIRECT_URL)
            # Okay, security check complete. Log the user in.
            create_superuser(request, form.data)
            return HttpResponseRedirect(redirect_to)
        else :
            context = {
                'form':form
            }
    else:
        form = registration_form(request)
        context = {
            'form': form,
            redirect_field_name: redirect_to
        }
    return TemplateResponse(request, template_name, context)

class SearchViewHtml(SearchView):
    template = 'partials/search-result.html'
    results_per_page = 10

class InvoiceViewHtml(TemplateView):
    template_name = 'invoice/invoice-result.html'

    def get_context_data(self, **kwargs):
        context = super(InvoiceViewHtml, self).get_context_data(**kwargs)
        context['invoice'] = models.Invoice.objects.get(pk=kwargs['invoiceid'])
        return context






class PatientViewSet(viewsets.ModelViewSet):
    model = models.Patient

    @detail_route(methods=['GET'])
    def examinations(self, request, pk=None):
        current_patient = self.get_object()
        examinations = models.Examination.objects.filter(patient=current_patient).order_by('-date')
        return Response(apiserializers.ExaminationSerializer(examinations, many=True).data)

    def pre_save(self, obj):
        """ Set the user which perform the operation as the currently logged user"""
        if not self.request.user.is_authenticated():
            raise Http404()
        obj.set_user_operation(self.request.user)




class RegularDoctorViewSet(viewsets.ModelViewSet):
    model = models.RegularDoctor





class ExaminationViewSet(viewsets.ModelViewSet):
    model = models.Examination


    @detail_route(methods=['POST'])
    def close(self, request, pk=None):
        current_examination = self.get_object()
        serializer = apiserializers.ExaminationInvoicingSerializer(data=request.DATA)
        if serializer.is_valid():
            if serializer.data['status'] == 'notinvoiced':
                current_examination.status = models.Examination.EXAMINATION_NOT_INVOICED
                current_examination.status_reason = serializer.data['reason']
                current_examination.save()
            if serializer.data['status'] == 'invoiced':
                current_examination.invoice = self.generate_invoice(serializer.data, )
                if serializer.data['paiment_mode'] == 'notpaid':
                    current_examination.status = models.Examination.EXAMINATION_WAITING_FOR_PAIEMENT
                    current_examination.save()
                if serializer.data['paiment_mode'] in ['check', 'cash']:
                    current_examination.status = models.Examination.EXAMINATION_INVOICED_PAID
                    current_examination.save()
            return Response({'invoicing':'try to execute the close'})
        else :
            return Response(serializer.errors,
                            status=status.HTTP_400_BAD_REQUEST)

    def generate_invoice(self, invoicingSerializerData):
        officesettings = models.OfficeSettings.objects.all()[0]
        therapeutsettings = models.TherapeutSettings.objects.filter(user=self.request.user)[0]

        invoice = models.Invoice()
        invoice.amount = invoicingSerializerData['amount']
        invoice.currency = officesettings.currency
        invoice.header = officesettings.invoice_office_header
        invoice.office_address_street = officesettings.office_address_street
        invoice.office_address_complement = officesettings.office_address_complement
        invoice.office_address_zipcode = officesettings.office_address_zipcode
        invoice.office_address_city = officesettings.office_address_city
        invoice.office_phone = officesettings.office_phone
        invoice.office_siret = officesettings.office_siret

        invoice.paiment_mode = invoicingSerializerData['paiment_mode']
        invoice.therapeut_name = self.request.user.last_name
        invoice.therapeut_first_name = self.request.user.first_name
        invoice.quality = therapeutsettings.quality
        invoice.adeli = therapeutsettings.adeli
        invoice.location = officesettings.office_address_city
        invoice.number = ""

        invoice.patient_family_name = self.get_object().patient.family_name
        invoice.patient_original_name = self.get_object().patient.original_name
        invoice.patient_first_name = self.get_object().patient.first_name
        invoice.patient_address_street = self.get_object().patient.address_street
        invoice.patient_address_complement = self.get_object().patient.address_complement
        invoice.patient_address_zipcode = self.get_object().patient.address_zipcode
        invoice.patient_address_city = self.get_object().patient.address_city
        invoice.content_invoice = officesettings.invoice_content
        invoice.footer = officesettings.invoice_footer
        invoice.date = datetime.today()
        invoice.save()
        invoice.number += unicode(10000+invoice.id)
        invoice.save()
        return invoice

    def pre_save(self, obj):
        if not self.request.user.is_authenticated():
            raise Http404()

        if not obj.therapeut:
            setattr(obj, 'therapeut', self.request.user)

    @detail_route(methods=['GET'])
    def comments(self, request, pk=None):
        current_examination = self.get_object()
        comments = models.ExaminationComment.objects.filter(examination=current_examination).order_by('-date')
        return Response(apiserializers.ExaminationCommentSerializer(comments, many=True).data)




class UserViewSet(viewsets.ModelViewSet):
    model = User
    serializer_class =  apiserializers.UserInfoSerializer
    permission_classes = [IsStaffOrTargetUser]







from .statistics import Statistics

class StatisticsView(APIView):

    def get(self, request, *args, **kwargs):
        myStats = Statistics(*args, **kwargs)
        result = myStats.compute()
        response = Response(result, status=status.HTTP_200_OK)
        return response

class InvoiceViewSet(viewsets.ReadOnlyModelViewSet):
    model = models.Invoice



class OfficeEventViewSet(viewsets.ReadOnlyModelViewSet):
    model = models.OfficeEvent
    serializer_class =  apiserializers.OfficeEventSerializer

    def get_queryset(self):
        """
        By default, filter events on only new patient/new examinations
        No update events are given.
        'all' parameter is used to get all events
        """
        queryset = models.OfficeEvent.objects.all()
        all_flag = self.request.QUERY_PARAMS.get('all', None)
        if all_flag is None :
            queryset = queryset.exclude(clazz__exact = 'Patient', type__exact=2 )
        return queryset

class OfficeSettingsView(viewsets.ModelViewSet):
    model = models.OfficeSettings
    serializer_class = apiserializers.OfficeSettingsSerializer
    permission_classes = [IsStaffOrTargetUser]

class TherapeutSettingsViewSet(viewsets.ModelViewSet):
    model = models.TherapeutSettings
    serializer_class = apiserializers.TherapeutSettingsSerializer
    permission_classes = [TargetUserSettingsPermissions]

    @list_route(permission_classes=[AllowAny])
    def get_by_user(self, request):
        if not self.request.user.is_authenticated():
            raise Http404()
        settings = models.TherapeutSettings.objects.filter(user=self.request.user)
        if (len(settings)>0):
            return Response(apiserializers.TherapeutSettingsSerializer(settings[0]).data)
        else:
            return Response({})

    def pre_save(self, obj):
        if not self.request.user.is_authenticated():
            raise Http404()

        if not obj.user:
            setattr(obj, 'user', self.request.user)

class ExaminationCommentViewSet(viewsets.ModelViewSet):
    model = models.ExaminationComment
    serializer_class = apiserializers.ExaminationCommentSerializer

    def pre_save(self, obj):
        setattr(obj, 'user', self.request.user)
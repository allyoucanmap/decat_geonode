# -*- coding: utf-8 -*-
#########################################################################
#
# Copyright (C) 2017 OSGeo
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
#########################################################################


from django.core.urlresolvers import reverse
from django.views.generic import TemplateView

from rest_framework import serializers
from rest_framework.routers import DefaultRouter
from rest_framework.pagination import PageNumberPagination
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet
from rest_framework_gis.serializers import GeoFeatureModelSerializer
from rest_framework_gis.pagination import GeoJsonPagination

from decat_geonode.models import (HazardAlert, HazardType,
                                  AlertSource, AlertSourceType,
                                  AlertLevel, Region)



class HazardTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = HazardType
        fields = ('name', 'description', 'icon',)


class AlertSourceTypeSerializer(serializers.ModelSerializer):

    class Meta:
        model = AlertSourceType
        fields = ('name', 'description', 'icon',)


class _AlertSourceSerializer(serializers.ModelSerializer):

    type = serializers.SlugRelatedField(read_only=True,
                                        many=False,
                                        slug_field='name')

    class Meta:
        model = AlertSource
        fields = ('type', 'name', 'uri',)


class AlertSourceSerializer(serializers.Serializer):
    type = serializers.CharField(max_length=32, required=True)
    name = serializers.CharField(max_length=255, required=True)
    uri = serializers.CharField(required=False, allow_null=True)

class AlertLevelSerializer(serializers.ModelSerializer):

    class Meta:
        model = AlertLevel
        fields = ('name', 'description', 'icon',)


class RegionSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=16)
    name = serializers.CharField(required=False)
    srid = serializers.CharField(required=False)


class HazardAlertSerializer(GeoFeatureModelSerializer):
    hazard_type = serializers.SlugRelatedField(many=False,
                                               read_only=False,
                                               queryset=HazardType.objects.all(),
                                               slug_field='name')
    source = AlertSourceSerializer(read_only=False)
    level = serializers.SlugRelatedField(many=False,
                                         read_only=False,
                                         queryset=AlertLevel.objects.all(),
                                         slug_field='name')
    regions = RegionSerializer(many=True, read_only=False)
    url = serializers.SerializerMethodField()

    class Meta:
        model = HazardAlert
        geo_field = 'geometry'
        fields = ('title', 'created_at', 'updated_at',
                  'description', 'reported_at', 'hazard_type',
                  'source', 'level', 'regions', 'promoted', 'id', 'url',)


    def get_url(self, obj):
        id = obj.id
        return reverse('decat-api:hazardalert-detail', args=(id,))

    def _process_validated_data(self, validated_data):

        _source = validated_data.pop('source', None)
        _regions = validated_data.pop('regions', None)
        if _source:

            source_type = AlertSourceType.objects.get(name=_source['type'])
            source, _ = AlertSource.objects.get_or_create(type=source_type, name=_source['name'])
            if _source.get('uri'):
                source.uri = _source['uri']
                source.save()
            validated_data['source'] = source            
        
        if _regions:
            regions = []
            for _r in _regions:
                regions.append(Region.objects.get(code=_r['code']))
            validated_data['regions'] = regions
        return validated_data

    def update(self, instance, validated_data):
        validated_data = self._process_validated_data(validated_data)
        regions = validated_data.pop('regions', None)

        for vname, val in validated_data.iteritems():
            setattr(instance, vname, val)
        if isinstance(regions, list):
            instance.regions.clear()
            instance.regions.add(*regions)
            instance.save()
        return instance

    def create(self, validated_data):
        validated_data = self._process_validated_data(validated_data)
        regions = validated_data.pop('regions')
        
        ha = HazardAlert.objects.create(**validated_data)
        ha.regions.add(*regions)
        ha.save()
        return ha



# geojson pagination enabler
class LocalGeoJsonPagination(GeoJsonPagination):
    page_size = 100


class LocalPagination(PageNumberPagination):
    page_size = 100


# views
class HazardAlertViewset(ModelViewSet):
    serializer_class = HazardAlertSerializer
    filter_fields = ['promoted', 'title', 'regions__name',
                     'regions__code', 'source__name',
                     'source__type__name', 'hazard_type__name',
                     'level__name']
    pagination_class = LocalGeoJsonPagination
    queryset = HazardAlert.objects.all()


class HazardTypesList(ReadOnlyModelViewSet):
    serializer_class = HazardTypeSerializer
    queryset = HazardType.objects.all()


class AlertLevelsList(ReadOnlyModelViewSet):
    serializer_class = AlertLevelSerializer
    queryset = AlertLevel.objects.all()


class AlertSourceTypeList(ReadOnlyModelViewSet):
    serializer_class = AlertSourceTypeSerializer
    queryset = AlertSourceType.objects.all()


class RegionList(ReadOnlyModelViewSet):
    serializer_class = RegionSerializer
    queryset = Region.objects.all()
    pagination_class = LocalPagination
    filter_fields = ['code', 'name']


router = DefaultRouter()
router.register('alerts', HazardAlertViewset)
router.register('hazard_types', HazardTypesList)
router.register('alert_levels', AlertLevelsList)
router.register('alert_sources/types', AlertSourceTypeList)
router.register('regions', RegionList)

# regular views

class IndexView(TemplateView):
    template_name = 'decat/index.html'


index_view = IndexView.as_view()

from django.contrib import admin
from .models import Incident, Comment, IncidentUpdate


class CommentInline(admin.TabularInline):
    model = Comment
    extra = 0
    readonly_fields = ['created_at']


class IncidentUpdateInline(admin.TabularInline):
    model = IncidentUpdate
    extra = 0
    readonly_fields = ['created_at']


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'severity', 'status', 'reported_by', 'created_at', 'location_description']
    list_filter = ['category', 'severity', 'status', 'created_at']
    search_fields = ['title', 'description', 'location_description', 'case_number']
    readonly_fields = ['created_at', 'updated_at', 'resolved_at']
    inlines = [CommentInline, IncidentUpdateInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'category', 'severity', 'status')
        }),
        ('Location', {
            'fields': ('latitude', 'longitude', 'location_description')
        }),
        ('Media', {
            'fields': ('image',)
        }),
        ('Reporting', {
            'fields': ('reported_by', 'is_anonymous')
        }),
        ('Assignment', {
            'fields': ('assigned_officer', 'resolved_by', 'resolved_at')
        }),
        ('Investigation', {
            'fields': ('case_number', 'investigation_notes')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_resolved', 'mark_as_investigating', 'mark_as_active']

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = super().get_readonly_fields(request, obj)
        if request.user.is_admin_user():
            return (*readonly_fields, 'status', 'assigned_officer')
        return readonly_fields

    def get_actions(self, request):
        actions = super().get_actions(request)
        if request.user.is_admin_user():
            for action in (
                'mark_as_resolved',
                'mark_as_investigating',
                'mark_as_active',
            ):
                actions.pop(action, None)
        return actions
    
    def mark_as_resolved(self, request, queryset):
        queryset.update(status='resolved')
        self.message_user(request, f'{queryset.count()} incidents marked as resolved.')
    mark_as_resolved.short_description = 'Mark selected incidents as resolved'
    
    def mark_as_investigating(self, request, queryset):
        queryset.update(status='investigating')
        self.message_user(request, f'{queryset.count()} incidents marked as under investigation.')
    mark_as_investigating.short_description = 'Mark selected incidents as under investigation'
    
    def mark_as_active(self, request, queryset):
        queryset.update(status='active')
        self.message_user(request, f'{queryset.count()} incidents marked as active.')
    mark_as_active.short_description = 'Mark selected incidents as active'


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ['incident', 'author', 'is_official', 'created_at']
    list_filter = ['is_official', 'created_at']
    search_fields = ['content', 'author__username', 'incident__title']


@admin.register(IncidentUpdate)
class IncidentUpdateAdmin(admin.ModelAdmin):
    list_display = ['incident', 'updated_by', 'old_status', 'new_status', 'created_at']
    list_filter = ['old_status', 'new_status', 'created_at']
    search_fields = ['incident__title', 'updated_by__username']
    readonly_fields = ['created_at']

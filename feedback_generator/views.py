from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import models
from .models import FeedbackRow
import json

def index(request):
    rows = FeedbackRow.objects.all().order_by('order')
    row_ids = list(rows.values_list('id', flat=True))
    return render(request, 'feedback_generator/index.html', {
        'rows': rows,
        'row_ids': json.dumps(row_ids)
    })

@csrf_exempt
def edit_row(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            row = get_object_or_404(FeedbackRow, id=data.get('id'))
            row.label = data.get('label', row.label)
            row.text_positive = data.get('text_positive', row.text_positive)
            row.text_negative = data.get('text_negative', row.text_negative)
            row.save()
            return JsonResponse({'status': 'success', 'message': 'Row updated successfully'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)

@csrf_exempt
def add_row(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            # Find next order
            max_order = FeedbackRow.objects.aggregate(models.Max('order'))['order__max']
            new_order = (max_order or 0) + 1
            
            FeedbackRow.objects.create(
                label=data.get('label', 'New Criteria'),
                text_positive=data.get('text_positive', ''),
                text_negative=data.get('text_negative', ''),
                order=new_order
            )
            return JsonResponse({'status': 'success', 'message': 'Row added successfully'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)

@csrf_exempt
def delete_row(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            row = get_object_or_404(FeedbackRow, id=data.get('id'))
            row.delete()
            return JsonResponse({'status': 'success', 'message': 'Row deleted successfully'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)

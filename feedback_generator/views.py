from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import models
from .models import FeedbackRow, Question
import json

def index(request):
    questions = Question.objects.prefetch_related('rows').all()
    # Serialize structure: { question_id: [row_ids] } for JS logic if needed, 
    # but primarily we just need row IDs for the copy/paste logic.
    # Actually, simpler to just list all row IDs flat or grouped.
    # Let's keep existing row_ids flat list for "generateText" simplicity across all tabs.
    rows = FeedbackRow.objects.all().order_by('question__order', 'order')
    row_ids = list(rows.values_list('id', flat=True))
    
    return render(request, 'feedback_generator/index.html', {
        'questions': questions,
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
            question_id = data.get('question_id')
            if not question_id:
                return JsonResponse({'status': 'error', 'message': 'Question ID required'}, status=400)
            
            question = get_object_or_404(Question, id=question_id)
            
            # Find next order in this question
            max_order = FeedbackRow.objects.filter(question=question).aggregate(models.Max('order'))['order__max']
            new_order = (max_order or 0) + 1
            
            FeedbackRow.objects.create(
                question=question,
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

@csrf_exempt
def add_question(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            # Find next order
            max_order = Question.objects.aggregate(models.Max('order'))['order__max']
            new_order = (max_order or 0) + 1
            
            Question.objects.create(
                text=data.get('text', 'New Question'),
                order=new_order
            )
            return JsonResponse({'status': 'success', 'message': 'Question added successfully'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)

@csrf_exempt
def delete_question(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            question = get_object_or_404(Question, id=data.get('id'))
            question.delete()
            return JsonResponse({'status': 'success', 'message': 'Question deleted successfully'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)

@csrf_exempt
def edit_question(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            question = get_object_or_404(Question, id=data.get('id'))
            question.text = data.get('text', question.text)
            question.save()
            return JsonResponse({'status': 'success', 'message': 'Question updated successfully'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)

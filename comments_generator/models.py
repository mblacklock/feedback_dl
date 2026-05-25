from django.db import models

class Question(models.Model):
    text = models.CharField(max_length=200, help_text="The question text (e.g., 'Introduction')")
    order = models.IntegerField(default=0, help_text="Order in which this question appears")

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.text

class FeedbackRow(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='rows', null=True, blank=True)
    label = models.CharField(max_length=200, blank=True, help_text="Optional label for the row (e.g., 'Structure', 'Content')")
    text_positive = models.TextField(help_text="Feedback text for the Positive option")
    text_negative = models.TextField(help_text="Feedback text for the Negative option")
    order = models.IntegerField(default=0, help_text="Order in which this row appears within the question")

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.label if self.label else f"Row {self.order}"

from django.db import models

class FeedbackRow(models.Model):
    label = models.CharField(max_length=200, blank=True, help_text="Optional label for the row (e.g., 'Introduction', 'Methodology')")
    text_positive = models.TextField(help_text="Feedback text for the Positive option")
    text_negative = models.TextField(help_text="Feedback text for the Negative option")
    order = models.IntegerField(default=0, help_text="Order in which this row appears on the form")

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.label if self.label else f"Row {self.order}"

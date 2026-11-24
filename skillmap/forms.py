from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from . import extract
from .models import JobDescription, Resume

User = get_user_model()

MIN_TEXT_CHARS = 40


class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")


class TextOrFileMixin:
    """Lets a form accept pasted text OR an uploaded PDF/DOCX/TXT for one field."""

    def resolve_text(self, text_field, file_field, label, max_chars):
        upload = self.cleaned_data.get(file_field)
        text = (self.cleaned_data.get(text_field) or "").strip()
        if upload:
            try:
                extracted = extract.extract_text(upload.name, upload.read())
            except extract.ExtractError as exc:
                self.add_error(file_field, str(exc))
                return None, ""
            return extracted[:max_chars], upload.name
        if len(text) < MIN_TEXT_CHARS:
            self.add_error(
                text_field, f"Paste your {label} (at least {MIN_TEXT_CHARS} characters) or upload a file."
            )
            return None, ""
        return text[:max_chars], ""


_FILE_HELP = "PDF, DOCX or TXT, up to 2 MB. The file itself is not stored; only its text is."


class QuickCheckForm(TextOrFileMixin, forms.Form):
    """Public home-page form. Nothing entered here is saved."""

    resume_text = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 10, "placeholder": "Paste your resume text here..."}),
        max_length=settings.MAX_RESUME_CHARS,
        label="Resume",
    )
    resume_file = forms.FileField(required=False, label="...or upload it", help_text=_FILE_HELP)
    job_text = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 10, "placeholder": "Paste the job description here..."}),
        max_length=settings.MAX_JOB_CHARS,
        min_length=MIN_TEXT_CHARS,
        label="Job description",
    )

    def clean(self):
        cleaned = super().clean()
        text, _ = self.resolve_text("resume_text", "resume_file", "resume", settings.MAX_RESUME_CHARS)
        if text is not None:
            cleaned["resume_text"] = text
        return cleaned


class ResumeForm(TextOrFileMixin, forms.Form):
    title = forms.CharField(max_length=80, help_text="e.g. 'Backend resume v2'")
    text = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 12}),
        max_length=settings.MAX_RESUME_CHARS,
        label="Resume text",
    )
    file = forms.FileField(required=False, label="...or upload it", help_text=_FILE_HELP)

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.extracted = ""
        self.source_filename = ""

    def clean(self):
        cleaned = super().clean()
        if self.user and Resume.objects.filter(user=self.user).count() >= settings.MAX_RESUMES_PER_USER:
            raise forms.ValidationError(
                f"You can keep at most {settings.MAX_RESUMES_PER_USER} resumes. Delete one first."
            )
        text, filename = self.resolve_text("text", "file", "resume", settings.MAX_RESUME_CHARS)
        if text is not None:
            self.extracted, self.source_filename = text, filename
        return cleaned

    def save(self):
        return Resume.objects.create(
            user=self.user,
            title=self.cleaned_data["title"],
            text=self.extracted,
            source_filename=self.source_filename,
        )


class JobForm(forms.ModelForm):
    class Meta:
        model = JobDescription
        fields = ("title", "company", "text")
        widgets = {"text": forms.Textarea(attrs={"rows": 14, "placeholder": "Paste the full job description"})}
        labels = {"text": "Job description"}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_text(self):
        text = self.cleaned_data["text"].strip()
        if len(text) < MIN_TEXT_CHARS:
            raise forms.ValidationError(f"Please paste at least {MIN_TEXT_CHARS} characters.")
        return text[: settings.MAX_JOB_CHARS]

    def clean(self):
        cleaned = super().clean()
        if self.user and JobDescription.objects.filter(user=self.user).count() >= settings.MAX_JOBS_PER_USER:
            raise forms.ValidationError(
                f"You can keep at most {settings.MAX_JOBS_PER_USER} job descriptions. Delete some first."
            )
        return cleaned


class AnalyzeForm(forms.Form):
    resume = forms.ModelChoiceField(queryset=Resume.objects.none(), empty_label=None)
    jobs = forms.ModelMultipleChoiceField(
        queryset=JobDescription.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        label="Job descriptions to compare against",
    )

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only the user's own rows can be chosen, so nobody can analyze someone else's data.
        self.fields["resume"].queryset = Resume.objects.filter(user=user)
        self.fields["jobs"].queryset = JobDescription.objects.filter(user=user)

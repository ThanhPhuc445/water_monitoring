from django.core.management.base import BaseCommand
from django.utils import timezone
from typing import Any, cast

from monitoring.models import Reading
from sensor_analysis.labeler import compute_label, LabelConfig


class Command(BaseCommand):
    help = "Label existing Reading rows as clean/dirty using strict WHO rules. Stores result in ai_prediction (1 safe/0 unsafe), ai_safe_probability (0-100), ai_quality_level, ai_risk_level, ai_recommendations."

    def add_arguments(self, parser):
        parser.add_argument('--allow-borderline-clean', action='store_true', help='If set, treat borderline as clean; otherwise strict (borderline -> dirty).')
        parser.add_argument('--device-id', type=int, default=None, help='Only label readings for a specific device ID')
        parser.add_argument('--limit', type=int, default=None, help='Limit number of rows to process')

    def handle(self, *args, **options):
        cfg = LabelConfig(strict=not options['allow_borderline_clean'])
        qs = Reading.objects.all().order_by('-timestamp')
        if options['device_id']:
            qs = qs.filter(device_id=options['device_id'])
        if options['limit']:
            qs = qs[: options['limit']]

        count = 0
        for r in qs.iterator():
            res = compute_label(r.ph, r.tds, r.ntu, cfg)
            # Map to AI fields
            is_clean = res['is_clean']
            r.ai_prediction = 1 if is_clean else 0
            # Map confidence to probability bands for visibility
            # confidence is 0..1 float; be defensive with casting
            raw_conf = res.get('confidence')
            try:
                conf_val = float(raw_conf) if raw_conf is not None else 0.0
            except (TypeError, ValueError):
                conf_val = 0.0
            safe_prob = round(100.0 * conf_val, 1) if is_clean else 0.0
            r.ai_safe_probability = safe_prob
            # Quality level mapping
            if is_clean and safe_prob >= 80:
                level = 'EXCELLENT'
            elif is_clean and safe_prob >= 60:
                level = 'GOOD'
            elif is_clean:
                level = 'FAIR'
            else:
                level = 'POOR'
            r.ai_quality_level = level
            r.ai_risk_level = 'LOW' if is_clean else 'HIGH'
            reasons = res.get('reasons')
            if reasons is None:
                reasons_list = []
            elif isinstance(reasons, list):
                reasons_list = [str(x) for x in reasons]
            else:
                reasons_list = [str(reasons)]
            # Ensure JSON-serializable list of strings
            r.ai_recommendations = cast(Any, reasons_list)
            r.ai_model_version = 'STRICT_RULES_v1.0'
            r.save(update_fields=[
                'ai_prediction', 'ai_safe_probability', 'ai_quality_level', 'ai_risk_level', 'ai_recommendations', 'ai_model_version'
            ])
            count += 1

        self.stdout.write(self.style.SUCCESS(f'Labeled {count} readings using strict WHO rules.'))

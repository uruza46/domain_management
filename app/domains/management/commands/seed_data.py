from datetime import date, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from approvals.models import Approval
from certificates.models import Certificate
from dns_info.models import DnsInfo, DnsRecord
from domains.models import Brand, Company, Domain, DomainHistory
from domains.osint_seed import seed_softbank_osint_data
from incidents.models import Incident
from monitoring.models import MonitoringTarget
from notifications.models import NotificationLog
from owners.models import Department, Employee, Employee2Department, Inventory, ManagementUnit
from registrars.models import RegistrarContract
from security.models import Risk, SecurityStatus


class Command(BaseCommand):
    help = "Seed local development data for domain management."

    def handle(self, *args, **options):
        password = getattr(settings, "SEED_ADMIN_PASSWORD", None) or "admin123"
        User = get_user_model()
        admin, _ = User.objects.update_or_create(
            username="admin",
            defaults={"is_staff": True, "is_superuser": True, "email": "admin@example.test"},
        )
        admin.set_password(password)
        admin.save()

        company, _ = Company.objects.update_or_create(
            company_code="C001",
            defaults={"company_name": "Example Holdings", "company_type": Company.TYPE_OWN, "is_active": True},
        )
        brand, _ = Brand.objects.update_or_create(
            brand_code="B001",
            defaults={"brand_name": "Example", "company": company, "trademark_keywords": "example", "is_active": True},
        )
        now = timezone.now()
        dept, _ = Department.objects.update_or_create(
            dept_code="D001",
            defaults={"dept_name": "IT本部", "dept_name_full": "Example Holdings / IT本部", "level": 2, "is_active": True, "start_at": now, "end_at": None},
        )
        if dept.honbu_id != dept.dept_code:
            dept.honbu = dept
            dept.save(update_fields=["honbu"])
        security_dept, _ = Department.objects.update_or_create(
            dept_code="D002",
            defaults={"dept_name": "セキュリティ本部", "dept_name_full": "Example Holdings / セキュリティ本部", "level": 2, "is_active": True, "start_at": now, "end_at": None},
        )
        if security_dept.honbu_id != security_dept.dept_code:
            security_dept.honbu = security_dept
            security_dept.save(update_fields=["honbu"])
        owner, _ = Employee.objects.update_or_create(
            employee_id="E001",
            defaults={"family_name": "山田", "given_name": "太郎", "family_name_kana": "ヤマダ", "given_name_kana": "タロウ", "email": "taro@example.test", "phone": "03-0000-0001", "is_active": True},
        )
        secondary, _ = Employee.objects.update_or_create(
            employee_id="E002",
            defaults={"family_name": "佐藤", "given_name": "花子", "family_name_kana": "サトウ", "given_name_kana": "ハナコ", "email": "hanako@example.test", "phone": "03-0000-0002", "is_active": True},
        )
        Employee2Department.objects.update_or_create(
            employee=owner,
            department=dept,
            defaults={"is_primary": True},
        )
        Employee2Department.objects.update_or_create(
            employee=secondary,
            department=security_dept,
            defaults={"is_primary": True},
        )
        Employee2Department.objects.update_or_create(
            employee=secondary,
            department=dept,
            defaults={"is_primary": False},
        )

        root_unit, _ = ManagementUnit.objects.update_or_create(
            unit_name="example.co.jp",
            defaults={
                "unit_type": ManagementUnit.UNIT_REGISTERED_DOMAIN,
                "setting_type": ManagementUnit.SETTING_INDIVIDUAL,
                "mgmt_dept": dept,
                "mgmt_owner": owner,
                "primary_owner": owner,
                "secondary_owner": secondary,
                "contact_email": "domain-admin@example.test",
                "check_status": ManagementUnit.CHECK_CONFIRMED,
                "next_check_at": date.today() + timedelta(days=365),
            },
        )
        child_unit, _ = ManagementUnit.objects.update_or_create(
            unit_name="dev.example.co.jp",
            defaults={
                "unit_type": ManagementUnit.UNIT_SUBDOMAIN_NAMESPACE,
                "parent_unit": root_unit,
                "setting_type": ManagementUnit.SETTING_INHERITED,
                "inherited_from_unit": root_unit,
                "contact_email": "domain-admin@example.test",
                "check_status": ManagementUnit.CHECK_CONFIRMED,
            },
        )

        domain, _ = Domain.objects.update_or_create(
            fqdn="example.co.jp",
            defaults={
                "domain_type": Domain.TYPE_CCTLD,
                "status": Domain.STATUS_ACTIVE,
                "mgmt_category": Domain.CATEGORY_INDIVIDUAL,
                "management_unit": root_unit,
                "company": company,
                "brand": brand,
                "registered_at": date(2020, 1, 1),
                "expires_at": date.today() + timedelta(days=180),
                "renewal_policy": Domain.RENEW_AUTO,
                "purpose": "コーポレートドメイン",
                "mail_enabled": True,
            },
        )
        subdomain, _ = Domain.objects.update_or_create(
            fqdn="api.dev.example.co.jp",
            defaults={
                "domain_type": Domain.TYPE_SUBDOMAIN,
                "status": Domain.STATUS_ACTIVE,
                "mgmt_category": Domain.CATEGORY_MANAGED,
                "management_unit": child_unit,
                "parent_domain": domain,
                "company": company,
                "brand": brand,
                "purpose": "開発API",
                "external_linked": True,
            },
        )

        RegistrarContract.objects.update_or_create(
            domain=domain,
            defaults={"registrar_name": "Example Registrar", "registrant_name": "Example Holdings", "contract_dept": dept, "renewal_method": RegistrarContract.METHOD_AUTO, "payer": owner, "transfer_allowed": True, "renewal_deadline": domain.expires_at, "renewal_notify_to": "domain-admin@example.test"},
        )
        DnsInfo.objects.update_or_create(
            domain=domain,
            defaults={"name_servers": "ns1.example.test\nns2.example.test", "dns_service": "Example DNS", "dnssec_enabled": True, "spf_status": DnsInfo.STATUS_SET, "dkim_status": DnsInfo.STATUS_SET, "dmarc_status": DnsInfo.STATUS_SET},
        )
        DnsRecord.objects.update_or_create(
            domain=domain,
            record_type=DnsRecord.TYPE_MX,
            name="example.co.jp",
            defaults={"value": "10 mail.example.co.jp", "ttl": 3600, "collected_at": timezone.now()},
        )
        Certificate.objects.update_or_create(
            subject_fqdn="example.co.jp",
            defaults={"domain": domain, "issuer": "Example CA", "expires_at": date.today() + timedelta(days=90), "issue_method": Certificate.METHOD_ACME, "renewal_method": Certificate.METHOD_ACME, "manager_contact": "domain-admin@example.test", "ct_detected": True},
        )
        SecurityStatus.objects.update_or_create(
            domain=domain,
            defaults={"dnssec": SecurityStatus.STATE_ENABLED, "registry_lock": SecurityStatus.STATE_UNKNOWN, "registrar_lock": SecurityStatus.STATE_ENABLED, "mfa": SecurityStatus.STATE_ENABLED, "takeover_protection": SecurityStatus.STATE_UNKNOWN, "cert_expiry_protection": SecurityStatus.STATE_ENABLED, "mail_spoofing_protection": SecurityStatus.STATE_ENABLED},
        )
        Risk.objects.update_or_create(
            domain=subdomain,
            management_unit=child_unit,
            risk_type=Risk.TYPE_TAKEOVER,
            defaults={"severity": Risk.SEV_MEDIUM, "source": Risk.SOURCE_AUTO, "detected_at": date.today(), "status": Risk.STATUS_OPEN, "assignee": secondary, "due_at": date.today() + timedelta(days=30)},
        )
        Inventory.objects.update_or_create(
            management_unit=root_unit,
            inventory_type=Inventory.TYPE_PERIODIC,
            requested_at=date.today(),
            defaults={"due_at": date.today() + timedelta(days=30), "check_status": ManagementUnit.CHECK_REQUESTED, "answered_by": owner},
        )
        MonitoringTarget.objects.update_or_create(
            candidate_fqdn="examp1e.co.jp",
            defaults={"detection_type": MonitoringTarget.TYPE_SIMILAR, "brand": brand, "source": MonitoringTarget.SOURCE_AUTO, "detected_at": date.today(), "confirm_status": MonitoringTarget.STATUS_UNCONFIRMED},
        )
        Incident.objects.update_or_create(
            domain=domain,
            management_unit=root_unit,
            occurred_at=timezone.now(),
            defaults={"content": "DNS設定変更の事後確認", "impact_scope": "影響なし", "status": Incident.STATUS_CLOSED, "prevention": "変更検知後の確認を継続する"},
        )
        Approval.objects.update_or_create(
            domain=domain,
            approval_type=Approval.TYPE_OWNER_CHANGE,
            requested_by=owner,
            requested_at=timezone.now(),
            defaults={"status": Approval.STATUS_PENDING, "payload_json": {"management_unit": root_unit.unit_name}},
        )
        NotificationLog.objects.update_or_create(
            dedup_key="seed-expiry-example-co-jp",
            defaults={"event_type": "domain_expiry", "domain": domain, "management_unit": root_unit, "recipient": "domain-admin@example.test", "sent_at": timezone.now(), "escalated": False},
        )
        DomainHistory.objects.create(
            target_type=DomainHistory.TARGET_DOMAIN,
            target_id=domain.id,
            change_category="seed",
            change_type="created",
            source=DomainHistory.SOURCE_MANUAL,
            changed_by=owner,
            reason="seed_data",
            diff_json={"created": True},
        )

        osint_counts = seed_softbank_osint_data()
        self.stdout.write(
            self.style.SUCCESS(
                "Seed data loaded. "
                f"SoftBank OSINT domains: {osint_counts['total']} "
                f"(roots: {osint_counts['roots']}, hosts: {osint_counts['hosts']}). "
                "Login with admin / SEED_ADMIN_PASSWORD."
            )
        )

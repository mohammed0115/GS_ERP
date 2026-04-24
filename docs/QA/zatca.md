# 🎯 Prompt كامل: تكامل ZATCA مع Django (إنتاجي)

> انسخ هذا الـ Prompt كاملاً والصقه في Claude أو ChatGPT أو أي AI آخر للحصول على نظام تكامل ZATCA كامل وجاهز للإنتاج.

---

## النص الكامل للـ Prompt

```
أريد منك بناء نظام تكامل احترافي وجاهز للإنتاج بين تطبيق Django (Python)
ومنصة فاتورة (Fatoora) التابعة لهيئة الزكاة والضريبة والجمارك السعودية (ZATCA)
لإصدار الفواتير الإلكترونية المتوافقة مع المرحلة الثانية (Integration Phase).

═══════════════════════════════════════════════════════════════
📌 السياق التقني
═══════════════════════════════════════════════════════════════

- **Framework**: Django 4.2+ مع Django REST Framework
- **Python**: 3.11+
- **قاعدة البيانات**: PostgreSQL 15+
- **Queue**: Celery 5.x مع Redis كـ broker و backend
- **المكتبات الأساسية**:
  * cryptography (للـ ECDSA و X.509)
  * lxml (لمعالجة XML)
  * signxml أو xmlsec (للـ XAdES signing)
  * qrcode[pil] (لتوليد QR)
  * requests (للـ HTTP)
  * reportlab أو weasyprint (لـ PDF)
  * pikepdf (لإنشاء PDF/A-3 مع embedded XML)

═══════════════════════════════════════════════════════════════
📋 المتطلبات الوظيفية الكاملة
═══════════════════════════════════════════════════════════════

### 1) أنواع المستندات المطلوب دعمها

النظام يصدر الفواتير لقطاعي B2B و B2C، لذا يجب دعم:

| الكود | النوع | آلية الإرسال | InvoiceTypeCode |
|-------|------|---------------|-----------------|
| 388 + 0100 | فاتورة ضريبية (B2B) | Clearance (فوري) | Standard Tax Invoice |
| 388 + 0200 | فاتورة مبسطة (B2C) | Reporting (24 ساعة) | Simplified Tax Invoice |
| 381 + 0100 | إشعار دائن (B2B) | Clearance | Credit Note |
| 381 + 0200 | إشعار دائن (B2C) | Reporting | Credit Note |
| 383 + 0100 | إشعار مدين (B2B) | Clearance | Debit Note |
| 383 + 0200 | إشعار مدين (B2C) | Reporting | Debit Note |

كل إشعار خصم/إضافة يجب أن يحتوي على:
- مرجع الفاتورة الأصلية (BillingReference > InvoiceDocumentReference)
- سبب الإصدار (PaymentMeans > InstructionNote)
- كود سبب الإصدار حسب ZATCA codes

### 2) توليد QR Code (TLV - Base64)

يجب دعم المرحلتين:

**المرحلة 1** (5 حقول):
- Tag 1: اسم البائع
- Tag 2: الرقم الضريبي (15 رقم)
- Tag 3: التاريخ والوقت بصيغة ISO 8601 (UTC)
- Tag 4: إجمالي الفاتورة شامل الضريبة (formatted: %.2f)
- Tag 5: مبلغ الضريبة (%.2f)

**المرحلة 2** (يضيف 4 حقول):
- Tag 6: SHA-256 hash للـ XML بصيغة Base64
- Tag 7: توقيع ECDSA بصيغة Base64
- Tag 8: المفتاح العام ECDSA (DER format) - bytes
- Tag 9: توقيع شهادة الهيئة (للفواتير المبسطة فقط)

التشفير: TLV حيث Tag = 1 byte, Length = 1 byte, Value = bytes
النتيجة كاملة تُشفّر Base64 وتوضع في QR Code (ECC level M).

### 3) بناء فاتورة XML (UBL 2.1 + KSA Extensions)

يجب أن تتضمن الفاتورة:

**الحقول الإلزامية**:
- ProfileID = "reporting:1.0"
- ID = رقم الفاتورة الفريد
- UUID = UUID v4 فريد لكل فاتورة
- IssueDate, IssueTime
- InvoiceTypeCode (مع attribute "name" حسب الجدول أعلاه)
- DocumentCurrencyCode = SAR
- TaxCurrencyCode = SAR

**AdditionalDocumentReference** (3 مراجع):
- ICV: Invoice Counter Value (تسلسل عام لكل الفواتير)
- PIH: Previous Invoice Hash (SHA-256 Base64 للفاتورة السابقة)
- QR: يُملأ بعد توليد الـ QR

**BillingReference** (للإشعارات فقط):
- InvoiceDocumentReference > ID = رقم الفاتورة الأصلية

**AccountingSupplierParty** (البائع):
- PartyIdentification (CRN - السجل التجاري)
- PostalAddress كامل (StreetName, BuildingNumber, PlotIdentification،
  CitySubdivisionName, CityName, PostalZone, Country)
- PartyTaxScheme (VAT number)
- PartyLegalEntity (RegistrationName)

**AccountingCustomerParty** (المشتري):
- نفس الحقول، مع تفاصيل إضافية للـ B2B

**InvoiceLine** لكل بند:
- ID, InvoicedQuantity (مع unitCode)
- LineExtensionAmount
- TaxTotal مع TaxAmount و RoundingAmount
- Item (Name, ClassifiedTaxCategory مع percent ومخطط VAT)
- Price (PriceAmount + AllowanceCharge للخصومات إن وجدت)

**TaxTotal** على مستوى الفاتورة:
- TaxAmount
- TaxSubtotal لكل فئة ضريبة (Standard 15%, Zero 0%, Exempt)

**LegalMonetaryTotal**:
- LineExtensionAmount
- TaxExclusiveAmount
- TaxInclusiveAmount
- AllowanceTotalAmount (إن وجد)
- PrepaidAmount (للمدفوع مسبقاً)
- PayableAmount

### 4) التوقيع الرقمي (XAdES-B-B الكامل)

⚠️ هذا الجزء حساس جداً وأي خطأ فيه = رفض الفاتورة من ZATCA.

**خوارزميات مطلوبة**:
- Hash: SHA-256
- Signature: ECDSA على منحنى secp256k1
- Canonicalization: Canonical XML 1.1 (C14N11)

**خطوات التوقيع**:

1. **Hash للـ Invoice**:
   - استخدم XPath transformations لإزالة:
     * UBLExtensions
     * AdditionalDocumentReference بـ ID="QR"
     * Signature element
   - طبّق C14N11 على الناتج
   - احسب SHA-256 → Base64

2. **بناء SignedProperties**:
   - SigningTime (UTC)
   - SigningCertificate > CertDigest (SHA-256 للشهادة)
   - تطبيق C14N11 → SHA-256 → Base64 → SignedPropertiesHash

3. **بناء SignedInfo**:
   - CanonicalizationMethod = C14N11
   - SignatureMethod = ECDSA-SHA256
   - Reference 1: على Invoice (مع InvoiceHash)
   - Reference 2: على SignedProperties (مع SignedPropertiesHash)
   - تطبيق C14N11 → SHA-256

4. **التوقيع**:
   - وقّع SignedInfo بالمفتاح الخاص ECDSA
   - النتيجة = SignatureValue

5. **بناء UBLExtensions** الكامل:
   ```
   UBLExtension > UBLExtensionURI = urn:oasis:names:specification:ubl:dsig:enveloped:xades
   ExtensionContent > UBLDocumentSignatures > SignatureInformation
   > Signature (ds:Signature element)
     - SignedInfo (مع References)
     - SignatureValue (Base64)
     - KeyInfo > X509Data > X509Certificate
     - Object > QualifyingProperties > SignedProperties
   ```

6. **حقن الـ Signature** داخل الـ XML الأصلي قبل ProfileID.

استخدم مكتبة signxml أو xmlsec بدلاً من بناء يدوي لتجنب الأخطاء.

### 5) Onboarding (تسجيل الجهاز)

**خطوات الـ Onboarding الكاملة**:

1. **توليد المفتاح الخاص**:
   - ECDSA على secp256k1
   - حفظ بصيغة PEM (PKCS#8)
   - يُفضّل تشفير المفتاح بـ passphrase في الإنتاج

2. **توليد CSR** بالشكل الذي تطلبه ZATCA:
   - Subject:
     * CN = اسم الحل
     * C = SA
     * O = اسم المنظمة
     * OU = اسم الفرع/الوحدة
   - Extensions:
     * SAN (DNSName) بصيغة:
       `1-{SolutionName}|2-{SerialNumber}|3-{VATNumber}`
     * BasicConstraints
     * KeyUsage (digitalSignature, nonRepudiation)
     * ExtendedKeyUsage
     * ZATCA-specific OIDs:
       - 2.5.4.4 (SerialNumber - معرّف الجهاز)
       - 2.5.4.97 (OrganizationIdentifier - الرقم الضريبي)
       - 2.5.4.10 (Organization)
       - Custom OID 1.3.6.1.4.1.311.20.2 (InvoiceType: 1100)
       - Location attribute
       - Industry attribute

3. **طلب Compliance CSID**:
   - POST /compliance
   - Headers: OTP, Accept-Version: V2
   - Body: { "csr": base64(CSR) }
   - الرد يحتوي على: binarySecurityToken, secret, requestID

4. **اختبار Compliance Invoices** (إجباري قبل Production):
   يجب اختبار 6 سيناريوهات على الأقل:
   - Standard Invoice
   - Standard Credit Note
   - Standard Debit Note
   - Simplified Invoice
   - Simplified Credit Note
   - Simplified Debit Note

5. **طلب Production CSID**:
   - POST /production/csids
   - Basic Auth بـ Compliance credentials
   - Body: { "compliance_request_id": "..." }

### 6) إرسال الفواتير لـ ZATCA

**Endpoints**:
- POST /invoices/clearance/single → للفواتير الضريبية B2B
- POST /invoices/reporting/single → للفواتير المبسطة B2C

**Headers مطلوبة**:
- Authorization: Basic {base64(CSID:Secret)}
- Content-Type: application/json
- Accept-Version: V2
- Accept-Language: en (أو ar)
- Clearance-Status: 0 للـ Reporting، 1 للـ Clearance

**Body**:
```json
{
  "invoiceHash": "Base64 SHA-256",
  "uuid": "UUID v4",
  "invoice": "Base64 من XML الموقّع كاملاً"
}
```

**معالجة الردود**:
- 200/202: نجح
  * تحقق من validationResults (warningMessages, errorMessages)
  * احفظ clearedInvoice (للـ Clearance)
- 303: مرفوض (يحتوي على رسائل أخطاء تفصيلية)
- 401: مشكلة في الـ Credentials
- 425: مرفوض بسبب أخطاء في الفاتورة

### 7) Celery Tasks (الإرسال غير المتزامن)

كل إرسال لـ ZATCA يجب أن يكون عبر Celery task مع:

**Task: submit_invoice_to_zatca**
- retry policy:
  * autoretry_for=(requests.RequestException, TimeoutError)
  * retry_backoff=True (exponential: 1m, 2m, 4m, 8m, 16m)
  * retry_kwargs={'max_retries': 5}
- timeout: 30 ثانية لكل محاولة
- في حالة الفشل النهائي: تحويل الحالة إلى "error" + إرسال إشعار

**Task: retry_failed_invoices** (يعمل كل ساعة)
- يبحث عن الفواتير في حالة "error" أو "pending"
- يحاول إعادة الإرسال
- ⚠️ تحقق من حد الـ 24 ساعة للفواتير المبسطة

**Task: verify_invoice_status**
- للتحقق من حالة الفاتورة من ZATCA دورياً

**Beat Schedule** (Celery Beat):
```python
'retry-failed-invoices': {
    'task': 'zatca.tasks.retry_failed_invoices',
    'schedule': crontab(minute=0),  # كل ساعة
},
'cleanup-old-failed': {
    'task': 'zatca.tasks.alert_overdue_simplified',
    'schedule': crontab(minute='*/30'),  # كل نصف ساعة
}
```

### 8) Django Admin Panel (احترافي)

**ZATCACredentialsAdmin**:
- عرض البيئة وحالة الاعتماد
- إخفاء الـ secret values (display only ****)
- زر "Test Connection" لاختبار الاتصال
- زر "Re-onboard" لإعادة التسجيل

**InvoiceAdmin**:
- list_display: invoice_number, type, status (مع لون)، total, issue_date, zatca_status
- list_filter: status, invoice_type, issue_date
- search_fields: invoice_number, buyer_name, buyer_vat_number, uuid
- readonly_fields: uuid, invoice_hash, signature, qr_code_tlv
- inlines: InvoiceLineInline
- actions:
  * resubmit_to_zatca (إعادة الإرسال)
  * download_xml
  * download_pdf_a3
  * print_qr_code
- fieldsets منظمة:
  * "البيانات الأساسية"
  * "الأطراف"
  * "الإجماليات"
  * "بيانات ZATCA"
  * "البيانات التشفيرية"

**Custom views**:
- /admin/zatca/dashboard/ → إحصائيات (عدد الفواتير، نسب القبول، الفواتير المعلّقة)
- /admin/zatca/invoice/<id>/preview/ → معاينة PDF
- /admin/zatca/invoice/<id>/zatca-response/ → عرض الرد الكامل من ZATCA

### 9) PDF/A-3 مع XML مضمّن

**المتطلبات**:
- صيغة PDF/A-3 (ISO 19005-3)
- XML الفاتورة مُضمّن كـ embedded file
- Metadata XMP صحيحة
- Color profile (sRGB)
- جميع الخطوط مُضمّنة

**محتويات الـ PDF**:
1. Header: شعار الشركة + بيانات البائع
2. عنوان: "فاتورة ضريبية" / "فاتورة مبسطة" / "إشعار دائن" / "إشعار مدين"
3. رقم الفاتورة + UUID + التاريخ
4. بيانات المشتري (للـ B2B)
5. جدول البنود (الكمية، السعر، الإجمالي، الضريبة)
6. الإجماليات
7. QR Code في الزاوية
8. Footer: ملاحظات + بيانات الاتصال

**حقن XML داخل PDF**:
استخدم pikepdf لإضافة الـ XML كـ AF (Associated File):
```python
pdf.attachments['invoice.xml'] = AttachedFileSpec(
    pdf, xml_content,
    description='ZATCA Invoice XML',
    relationship='/Source',
    mime_type='application/xml'
)
```

═══════════════════════════════════════════════════════════════
🏗️ هيكل المشروع المطلوب
═══════════════════════════════════════════════════════════════

```
zatca_integration/
├── apps/
│   └── zatca/
│       ├── __init__.py
│       ├── apps.py
│       ├── admin.py                    # Django Admin مخصص
│       ├── models.py                   # Invoice, InvoiceLine, Credentials, Logs
│       ├── views.py                    # REST API endpoints
│       ├── urls.py
│       ├── serializers.py              # DRF Serializers
│       ├── tasks.py                    # Celery tasks
│       ├── signals.py                  # Django signals
│       ├── exceptions.py               # Custom exceptions
│       ├── services/
│       │   ├── __init__.py
│       │   ├── invoice_service.py      # الخدمة الرئيسية
│       │   ├── xml_builder.py          # بناء UBL 2.1 XML
│       │   ├── xml_signer.py           # XAdES-B-B signing
│       │   ├── qr_generator.py         # TLV QR codes
│       │   ├── pdf_generator.py        # PDF/A-3 with embedded XML
│       │   ├── api_client.py           # ZATCA HTTP client
│       │   ├── signer.py               # ECDSA + Cert management
│       │   └── csr_generator.py        # توليد CSR
│       ├── validators/
│       │   ├── __init__.py
│       │   ├── invoice_validator.py    # validation قبل الإرسال
│       │   └── zatca_response_parser.py
│       ├── management/
│       │   └── commands/
│       │       ├── zatca_onboard.py    # أمر Onboarding
│       │       ├── zatca_test.py       # اختبار Compliance
│       │       └── zatca_resubmit.py   # إعادة إرسال يدوي
│       ├── migrations/
│       └── tests/
│           ├── test_qr_generator.py
│           ├── test_xml_builder.py
│           ├── test_xml_signer.py
│           ├── test_api_client.py
│           ├── test_invoice_service.py
│           └── fixtures/
│               └── sample_invoices.json
├── config/
│   ├── settings/
│   │   ├── base.py
│   │   ├── development.py
│   │   ├── production.py
│   │   └── zatca_config.py             # إعدادات ZATCA
│   ├── celery.py
│   └── urls.py
├── docker/
│   ├── Dockerfile
│   ├── docker-compose.yml              # Django + mysql + Redis + Celery
│   └── docker-compose.prod.yml
├── requirements/
│   ├── base.txt
│   ├── development.txt
│   └── production.txt
├── docs/
│   ├── README.md                       # توثيق رئيسي بالعربية
│   ├── ONBOARDING.md                   # دليل الـ Onboarding خطوة بخطوة
│   ├── API.md                          # توثيق REST API
│   ├── DEPLOYMENT.md                   # دليل النشر للإنتاج
│   └── TROUBLESHOOTING.md              # حل المشاكل الشائعة
└── manage.py
```

═══════════════════════════════════════════════════════════════
🌐 بيئات ZATCA
═══════════════════════════════════════════════════════════════

| البيئة | URL | الاستخدام |
|--------|-----|----------|
| Sandbox | https://gw-fatoora.zatca.gov.sa/e-invoicing/developer-portal | تطوير وتجارب أولية |
| Simulation | https://gw-fatoora.zatca.gov.sa/e-invoicing/simulation | محاكاة الإنتاج |
| Production | https://gw-fatoora.zatca.gov.sa/e-invoicing/core | الإنتاج الفعلي |

النظام يجب أن يدعم التبديل بين البيئات عبر settings فقط.

═══════════════════════════════════════════════════════════════
🔐 متطلبات الأمان
═══════════════════════════════════════════════════════════════

1. **حفظ المفاتيح الخاصة**:
   - في الإنتاج: HashiCorp Vault أو AWS Secrets Manager أو HSM
   - مطلقاً لا تحفظها في git أو في قاعدة البيانات بدون تشفير

2. **تشفير الـ CSID Secrets** في قاعدة البيانات باستخدام django-cryptography
3. **Rate limiting** على الـ API endpoints
4. **Logging** كل العمليات الحساسة (audit log)
5. **CSRF protection** + JWT/Token auth للـ REST API
6. **HTTPS only** في الإنتاج
7. **IP Whitelisting** لـ ZATCA (إن لزم)

═══════════════════════════════════════════════════════════════
📊 متطلبات الجودة
═══════════════════════════════════════════════════════════════

1. **Test Coverage**: ≥ 80%
2. **Type hints**: استخدم type hints في كل الدوال
3. **Linting**: black + isort + flake8 + mypy
4. **Error handling**: Custom exceptions واضحة
5. **Logging**: استخدم Python logging مع مستويات مناسبة
6. **Documentation**:
   - Docstrings لكل class و function
   - README كامل بالعربية
   - شرح كل خطوة من Onboarding بالصور
   - أمثلة API كاملة
7. **API Documentation**: OpenAPI/Swagger via drf-spectacular

═══════════════════════════════════════════════════════════════
✅ معايير القبول (Acceptance Criteria)
═══════════════════════════════════════════════════════════════

النظام يعتبر جاهز عندما:

1. ✅ يمر بنجاح من اختبارات Compliance لـ ZATCA الستة
2. ✅ يصدر فواتير ضريبية ومبسطة وإشعارات خصم/إضافة بشكل صحيح
3. ✅ يولّد PDF/A-3 صالح (تحقق بـ veraPDF)
4. ✅ يعالج الإشعارات (Credit/Debit) مع المراجع الصحيحة
5. ✅ Celery يعيد المحاولة تلقائياً عند فشل الإرسال
6. ✅ Admin Panel يعرض الفواتير والإحصائيات بشكل واضح
7. ✅ كل الـ tests تمر بنجاح
8. ✅ التوثيق كامل بالعربية

═══════════════════════════════════════════════════════════════
📚 المراجع الرسمية
═══════════════════════════════════════════════════════════════

- E-Invoicing Detailed Guidelines: 
  https://zatca.gov.sa/en/E-Invoicing/Introduction/Guidelines/
- Developer Portal Manual
- XML Implementation Standard
- Security Features Implementation Standards
- Fatoora Portal: https://fatoora.zatca.gov.sa

═══════════════════════════════════════════════════════════════
🚀 ابدأ الآن
═══════════════════════════════════════════════════════════════

ابنِ المشروع كاملاً على مراحل:

**المرحلة 1**: الهيكل الأساسي + Models + Settings
**المرحلة 2**: QR Generator + XML Builder + Tests
**المرحلة 3**: ECDSA Signer + CSR Generator + XAdES Signing
**المرحلة 4**: API Client + Onboarding command
**المرحلة 5**: Invoice Service الرئيسية + Validators
**المرحلة 6**: Celery Tasks + Beat Schedule
**المرحلة 7**: Django Admin + Custom views
**المرحلة 8**: PDF/A-3 Generator
**المرحلة 9**: REST API + Serializers + Documentation
**المرحلة 10**: Docker setup + Deployment docs

في كل مرحلة:
- اكتب الكود مع type hints
- اكتب tests
- وثّق في README
- أعطني ملخص لما تم إنجازه قبل الانتقال للمرحلة التالية

ابدأ بالمرحلة 1 الآن.
```

---

## 💡 نصائح لاستخدام هذا الـ Prompt

### ✅ افعل
- **قسّمه على مراحل**: لا تطلب كل شيء دفعة واحدة. ابدأ بالمرحلة 1 وانتظر النتيجة قبل طلب التالية
- **اطلب الـ tests مع كل مرحلة** للتأكد من جودة الكود
- **راجع كود XAdES يدوياً** — هذا أكثر جزء يفشل في فواتير ZATCA
- **اختبر في Sandbox أولاً** قبل Simulation قبل Production

### ❌ لا تفعل
- لا تنشر للإنتاج بدون اجتياز اختبارات Simulation الكاملة
- لا تحفظ الـ Private Keys في git أو ملفات نصية عادية
- لا تتجاهل warning messages من ZATCA (قد تتحول لأخطاء لاحقاً)
- لا تنسَ نسخ احتياطي يومي للمفاتيح والشهادات

### 🔧 لتخصيصه أكثر
أضف في نهاية الـ Prompt قبل "ابدأ بالمرحلة 1":

```
بيانات شركتي للاختبار:
- اسم الشركة: [اسم شركتك]
- الرقم الضريبي: [15 رقم]
- السجل التجاري: [10 أرقام]
- العنوان: [الشارع، المدينة، الرمز البريدي]
- اسم الحل التقني: [اسم النظام]
- متوسط عدد الفواتير اليومية: [العدد]
```

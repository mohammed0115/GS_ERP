# توثيق واجهات API - نظام ERP سحابي

## نظرة عامة

هذه الوثيقة تصف واجهات برمجة التطبيقات (API) لنظام ERP السحابي المماثل لدفترة. النظام يوفر RESTful API كامل + GraphQL للاستعلامات المركبة.

- **Base URL (Production):** `https://api.example.com/v1`
- **Base URL (Sandbox):** `https://api-sandbox.example.com/v1`
- **Format:** JSON
- **Auth:** OAuth 2.0 + JWT
- **Documentation:** OpenAPI 3.1 (Swagger)
- **Rate Limit:** 1000 طلب/دقيقة لكل مفتاح API

---

## 1. المصادقة (Authentication)

### 1.1 تسجيل الدخول

```http
POST /v1/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "SecurePass123!",
  "tenant_subdomain": "mycompany"
}
```

**Response 200 OK:**
```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJSUzI1NiIs...",
  "token_type": "Bearer",
  "expires_in": 900,
  "user": {
    "id": 42,
    "email": "user@example.com",
    "first_name": "أحمد",
    "last_name": "السعيد",
    "tenant_id": "a3f5b2c1-1234-5678-9abc-def012345678",
    "roles": ["admin"]
  }
}
```

### 1.2 تجديد الـ Access Token

```http
POST /v1/auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJhbGciOiJSUzI1NiIs..."
}
```

### 1.3 تسجيل الخروج

```http
POST /v1/auth/logout
Authorization: Bearer {access_token}
```

### 1.4 الحصول على بيانات المستخدم الحالي

```http
GET /v1/auth/me
Authorization: Bearer {access_token}
```

### 1.5 ترويسات مطلوبة في كل طلب

```http
Authorization: Bearer {access_token}
X-Tenant-ID: {tenant_uuid}
Content-Type: application/json
Accept-Language: ar
```

---

## 2. العملاء (Customers)

### 2.1 قائمة العملاء

```http
GET /v1/customers?page=1&per_page=25&search=محمد&type=business&is_active=true&sort=-created_at
```

**Query Parameters:**

| المعامل | النوع | الوصف |
|---------|------|--------|
| `page` | int | رقم الصفحة (افتراضي 1) |
| `per_page` | int | عدد العناصر لكل صفحة (افتراضي 25، أقصى 100) |
| `search` | string | بحث في الاسم، البريد، الهاتف |
| `type` | string | individual / business |
| `is_active` | bool | true / false |
| `sort` | string | `field` للتصاعدي، `-field` للتنازلي |

**Response 200 OK:**
```json
{
  "data": [
    {
      "id": 1024,
      "customer_number": "CUS-00001024",
      "type": "business",
      "name": "شركة الأمل التجارية",
      "name_ar": "شركة الأمل التجارية",
      "email": "info@alamal.sa",
      "phone": "+966501234567",
      "tax_number": "300123456700003",
      "country_code": "SA",
      "city": "الدمام",
      "credit_limit": 50000.00,
      "balance": 12500.00,
      "is_active": true,
      "created_at": "2026-01-15T10:30:00Z"
    }
  ],
  "meta": {
    "current_page": 1,
    "per_page": 25,
    "total": 1547,
    "last_page": 62
  },
  "links": {
    "self": "/v1/customers?page=1",
    "next": "/v1/customers?page=2",
    "last": "/v1/customers?page=62"
  }
}
```

### 2.2 إنشاء عميل جديد

```http
POST /v1/customers
Content-Type: application/json

{
  "type": "business",
  "name": "شركة الأمل التجارية",
  "email": "info@alamal.sa",
  "phone": "+966501234567",
  "tax_number": "300123456700003",
  "country_code": "SA",
  "city": "الدمام",
  "address_line1": "حي الفيصلية، شارع الملك فهد",
  "credit_limit": 50000.00,
  "payment_terms_days": 30,
  "custom_fields": {
    "sales_rep": "خالد العتيبي",
    "industry": "تجارة جملة"
  }
}
```

### 2.3 تفاصيل عميل

```http
GET /v1/customers/{id}
```

### 2.4 تعديل عميل

```http
PUT /v1/customers/{id}
PATCH /v1/customers/{id}
```

### 2.5 حذف عميل (Soft Delete)

```http
DELETE /v1/customers/{id}
```

### 2.6 فواتير عميل

```http
GET /v1/customers/{id}/invoices
GET /v1/customers/{id}/payments
GET /v1/customers/{id}/statement?from=2026-01-01&to=2026-04-30
```

---

## 3. المنتجات (Products)

### 3.1 قائمة المنتجات

```http
GET /v1/products?search=لابتوب&category_id=10&is_active=true
```

### 3.2 إنشاء منتج

```http
POST /v1/products
Content-Type: application/json

{
  "sku": "LAP-DELL-001",
  "barcode": "1234567890123",
  "name": "Dell Laptop XPS 15",
  "name_ar": "لابتوب ديل XPS 15",
  "description": "Intel i7, 16GB RAM, 512GB SSD",
  "category_id": 10,
  "type": "product",
  "unit": "piece",
  "cost_price": 4500.00,
  "selling_price": 5500.00,
  "tax_rate": 0.15,
  "track_inventory": true,
  "reorder_point": 5
}
```

### 3.3 رصيد منتج في المستودعات

```http
GET /v1/products/{id}/stock
```

```json
{
  "product_id": 501,
  "total_quantity": 47,
  "warehouses": [
    { "warehouse_id": 1, "warehouse_name": "المستودع الرئيسي", "quantity": 30, "reserved": 5, "available": 25 },
    { "warehouse_id": 2, "warehouse_name": "فرع جدة", "quantity": 17, "reserved": 0, "available": 17 }
  ]
}
```

---

## 4. الفواتير (Invoices)

### 4.1 قائمة الفواتير

```http
GET /v1/invoices?status=sent&from=2026-04-01&to=2026-04-30&customer_id=1024
```

### 4.2 إصدار فاتورة جديدة

```http
POST /v1/invoices
Content-Type: application/json

{
  "customer_id": 1024,
  "issue_date": "2026-04-25",
  "due_date": "2026-05-25",
  "currency": "SAR",
  "items": [
    {
      "product_id": 501,
      "description": "لابتوب ديل XPS 15",
      "quantity": 2,
      "unit_price": 5500.00,
      "discount_pct": 0.05,
      "tax_rate": 0.15,
      "warehouse_id": 1
    },
    {
      "description": "خدمة تركيب وتدريب",
      "quantity": 1,
      "unit_price": 500.00,
      "tax_rate": 0.15
    }
  ],
  "notes": "شكراً لتعاملكم معنا",
  "terms": "السداد خلال 30 يوم",
  "send_to_zatca": true,
  "send_email": true
}
```

**Response 201 Created:**
```json
{
  "id": 88421,
  "invoice_number": "INV-2026-00021",
  "uuid": "9b2e1a5c-7f3d-4e8b-a1c2-5d6e7f8a9b0c",
  "status": "sent",
  "issue_date": "2026-04-25",
  "due_date": "2026-05-25",
  "customer": {
    "id": 1024,
    "name": "شركة الأمل التجارية"
  },
  "subtotal": 11050.00,
  "discount_total": 550.00,
  "tax_total": 1575.00,
  "total": 12075.00,
  "balance_due": 12075.00,
  "qr_code": "AQxBQyBDby4=...",
  "pdf_url": "https://api.example.com/v1/invoices/88421/pdf",
  "zatca": {
    "status": "cleared",
    "uuid": "9b2e1a5c-7f3d-4e8b-a1c2-5d6e7f8a9b0c",
    "cleared_at": "2026-04-25T14:32:18Z"
  },
  "items": [ /* ... */ ],
  "created_at": "2026-04-25T14:32:00Z"
}
```

### 4.3 تفاصيل فاتورة

```http
GET /v1/invoices/{id}
```

### 4.4 تنزيل PDF للفاتورة

```http
GET /v1/invoices/{id}/pdf
Accept: application/pdf
```

### 4.5 إلغاء فاتورة

```http
POST /v1/invoices/{id}/cancel
Content-Type: application/json

{
  "reason": "خطأ في الكمية"
}
```

### 4.6 تسجيل دفعة على فاتورة

```http
POST /v1/invoices/{id}/payments
Content-Type: application/json

{
  "payment_date": "2026-04-30",
  "method": "bank_transfer",
  "amount": 5000.00,
  "reference": "REF-78912",
  "bank_account_id": 3,
  "notes": "دفعة جزئية"
}
```

### 4.7 إعادة إرسال للـ ZATCA

```http
POST /v1/invoices/{id}/zatca/clear
```

### 4.8 إنشاء إشعار دائن (Credit Note)

```http
POST /v1/invoices/{id}/credit-notes
Content-Type: application/json

{
  "issue_date": "2026-04-26",
  "reason": "إرجاع منتج معيب",
  "items": [
    {
      "invoice_item_id": 7654,
      "quantity": 1,
      "unit_price": 5500.00
    }
  ]
}
```

---

## 5. المدفوعات (Payments)

### 5.1 قائمة المدفوعات

```http
GET /v1/payments?type=received&from=2026-04-01&to=2026-04-30
```

### 5.2 تسجيل مدفوعة جديدة (غير مرتبطة بفاتورة)

```http
POST /v1/payments
Content-Type: application/json

{
  "payment_type": "received",
  "customer_id": 1024,
  "payment_date": "2026-04-30",
  "method": "cash",
  "amount": 1500.00,
  "currency": "SAR",
  "notes": "دفعة على الحساب",
  "allocations": [
    { "invoice_id": 88421, "amount": 1500.00 }
  ]
}
```

---

## 6. المخزون (Inventory)

### 6.1 أرصدة المخزون

```http
GET /v1/inventory/stock?warehouse_id=1&low_stock=true
```

### 6.2 حركة مخزون يدوية (تعديل/جرد)

```http
POST /v1/inventory/movements
Content-Type: application/json

{
  "warehouse_id": 1,
  "movement_type": "adjustment_in",
  "items": [
    {
      "product_id": 501,
      "quantity": 5,
      "unit_cost": 4500.00,
      "notes": "تسوية بعد الجرد"
    }
  ]
}
```

### 6.3 تحويل مخزون بين المستودعات

```http
POST /v1/inventory/transfers
Content-Type: application/json

{
  "from_warehouse_id": 1,
  "to_warehouse_id": 2,
  "transfer_date": "2026-04-25",
  "items": [
    { "product_id": 501, "quantity": 10 }
  ]
}
```

---

## 7. المحاسبة (Accounting)

### 7.1 دليل الحسابات

```http
GET /v1/accounting/chart-of-accounts
```

```json
{
  "data": [
    {
      "id": 1,
      "code": "1",
      "name": "الأصول",
      "type": "asset",
      "is_group": true,
      "children": [
        {
          "id": 2,
          "code": "11",
          "name": "الأصول المتداولة",
          "is_group": true,
          "children": [
            { "id": 3, "code": "1101", "name": "الصندوق", "balance": 25000.00 }
          ]
        }
      ]
    }
  ]
}
```

### 7.2 إنشاء قيد يدوي

```http
POST /v1/accounting/journal-entries
Content-Type: application/json

{
  "entry_date": "2026-04-25",
  "description": "تسجيل مصروف إيجار شهر أبريل",
  "lines": [
    { "account_id": 250, "debit": 10000.00, "cost_center_id": 5 },
    { "account_id": 101, "credit": 10000.00 }
  ]
}
```

### 7.3 ترحيل القيد (Posting)

```http
POST /v1/accounting/journal-entries/{id}/post
```

---

## 8. التقارير (Reports)

### 8.1 الميزانية العمومية

```http
GET /v1/reports/balance-sheet?as_of=2026-04-30
```

### 8.2 قائمة الدخل (الأرباح والخسائر)

```http
GET /v1/reports/profit-loss?from=2026-01-01&to=2026-03-31&compare=last_year
```

### 8.3 ميزان المراجعة

```http
GET /v1/reports/trial-balance?as_of=2026-04-30
```

### 8.4 التدفقات النقدية

```http
GET /v1/reports/cash-flow?from=2026-01-01&to=2026-03-31
```

### 8.5 تقرير المبيعات

```http
GET /v1/reports/sales?group_by=customer&from=2026-04-01&to=2026-04-30
```

### 8.6 تقرير المخزون

```http
GET /v1/reports/inventory-valuation?as_of=2026-04-30&warehouse_id=1
```

### 8.7 تصدير التقارير

```http
GET /v1/reports/profit-loss?from=2026-01-01&to=2026-03-31&format=pdf
GET /v1/reports/profit-loss?from=2026-01-01&to=2026-03-31&format=xlsx
GET /v1/reports/profit-loss?from=2026-01-01&to=2026-03-31&format=csv
```

---

## 9. الموارد البشرية (HR)

### 9.1 قائمة الموظفين

```http
GET /v1/hr/employees?department_id=3&is_active=true
```

### 9.2 تسجيل حضور

```http
POST /v1/hr/attendance/check-in
Content-Type: application/json

{
  "employee_id": 42,
  "location": { "lat": 26.4207, "lng": 50.0888 }
}
```

### 9.3 طلب إجازة

```http
POST /v1/hr/leave-requests
Content-Type: application/json

{
  "employee_id": 42,
  "leave_type": "annual",
  "start_date": "2026-05-15",
  "end_date": "2026-05-22",
  "reason": "إجازة عائلية"
}
```

### 9.4 تشغيل مسير الرواتب

```http
POST /v1/hr/payroll-runs
Content-Type: application/json

{
  "period_year": 2026,
  "period_month": 4,
  "include_employees": "all"  // أو ["1","2","3"]
}
```

---

## 10. Webhooks

### 10.1 تسجيل Webhook

```http
POST /v1/webhooks
Content-Type: application/json

{
  "url": "https://my-app.com/webhooks/erp",
  "events": [
    "invoice.created",
    "invoice.paid",
    "invoice.cancelled",
    "payment.received",
    "customer.created",
    "stock.low"
  ]
}
```

### 10.2 شكل Webhook Event عند الإرسال

```http
POST https://my-app.com/webhooks/erp
Content-Type: application/json
X-Webhook-Signature: sha256=abc123...
X-Webhook-Event: invoice.paid
X-Webhook-Delivery: a3f5b2c1-...

{
  "event": "invoice.paid",
  "tenant_id": "a3f5b2c1-...",
  "timestamp": "2026-04-30T10:15:00Z",
  "data": {
    "id": 88421,
    "invoice_number": "INV-2026-00021",
    "total": 12075.00,
    "paid_at": "2026-04-30T10:15:00Z"
  }
}
```

### 10.3 التحقق من توقيع HMAC

```javascript
// Node.js Example
const crypto = require('crypto');
const signature = req.headers['x-webhook-signature'];
const expected = 'sha256=' + crypto
  .createHmac('sha256', WEBHOOK_SECRET)
  .update(JSON.stringify(req.body))
  .digest('hex');

if (signature !== expected) {
  return res.status(401).send('Invalid signature');
}
```

### الأحداث المدعومة:

| الحدث | الوصف |
|--------|--------|
| `invoice.created` | فاتورة جديدة |
| `invoice.sent` | تم إرسالها للعميل |
| `invoice.paid` | تم سداد الفاتورة كاملة |
| `invoice.partially_paid` | سداد جزئي |
| `invoice.cancelled` | تم إلغاء الفاتورة |
| `invoice.zatca_cleared` | تم اعتماد الفاتورة من ZATCA |
| `payment.received` | استلام دفعة |
| `customer.created` | عميل جديد |
| `customer.updated` | تعديل عميل |
| `product.created` | منتج جديد |
| `stock.low` | منتج وصل لحد إعادة الطلب |
| `purchase_order.received` | استلام بضاعة |
| `employee.hired` | تعيين موظف جديد |
| `payroll.completed` | اكتمال مسير الرواتب |

---

## 11. أكواد الأخطاء (Error Codes)

### الشكل العام للخطأ

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "البيانات المُرسَلة غير صحيحة",
    "message_en": "The provided data is invalid",
    "details": [
      {
        "field": "email",
        "message": "البريد الإلكتروني غير صالح"
      }
    ],
    "request_id": "req_a3f5b2c1..."
  }
}
```

### رموز HTTP المستخدمة

| الكود | المعنى |
|------|---------|
| `200 OK` | نجاح |
| `201 Created` | تم الإنشاء |
| `204 No Content` | نجاح بدون محتوى (delete) |
| `400 Bad Request` | طلب غير صالح |
| `401 Unauthorized` | لم يتم المصادقة |
| `403 Forbidden` | لا تملك الصلاحية |
| `404 Not Found` | المورد غير موجود |
| `409 Conflict` | تعارض (مثل تكرار) |
| `422 Unprocessable Entity` | فشل التحقق من البيانات |
| `429 Too Many Requests` | تجاوز حد الطلبات |
| `500 Internal Server Error` | خطأ في الخادم |
| `502 Bad Gateway` | خدمة تابعة غير متاحة (مثل ZATCA) |

### أكواد التطبيق الشائعة

| الكود | الوصف |
|------|--------|
| `VALIDATION_ERROR` | فشل التحقق من المدخلات |
| `AUTH_INVALID_CREDENTIALS` | بيانات دخول خاطئة |
| `AUTH_TOKEN_EXPIRED` | انتهت صلاحية الـ token |
| `AUTH_MFA_REQUIRED` | المصادقة الثنائية مطلوبة |
| `PERMISSION_DENIED` | لا تملك الصلاحية |
| `RESOURCE_NOT_FOUND` | المورد غير موجود |
| `DUPLICATE_RESOURCE` | المورد موجود مسبقاً |
| `INSUFFICIENT_STOCK` | المخزون غير كافٍ |
| `CREDIT_LIMIT_EXCEEDED` | تجاوز سقف ائتمان العميل |
| `JOURNAL_NOT_BALANCED` | القيد غير متوازن |
| `PERIOD_LOCKED` | الفترة المحاسبية مغلقة |
| `ZATCA_VALIDATION_FAILED` | فشل التحقق لدى ZATCA |
| `ZATCA_SERVICE_UNAVAILABLE` | خدمة ZATCA غير متاحة حالياً |
| `RATE_LIMIT_EXCEEDED` | تجاوز حد الطلبات |
| `PLAN_LIMIT_REACHED` | الباقة الحالية لا تسمح بهذه العملية |

---

## 12. أمثلة بلغات مختلفة

### Node.js (axios)

```javascript
const axios = require('axios');

const client = axios.create({
  baseURL: 'https://api.example.com/v1',
  headers: {
    'Authorization': `Bearer ${ACCESS_TOKEN}`,
    'X-Tenant-ID': TENANT_ID,
    'Content-Type': 'application/json'
  }
});

// إصدار فاتورة
const invoice = await client.post('/invoices', {
  customer_id: 1024,
  issue_date: '2026-04-25',
  items: [
    { product_id: 501, quantity: 2, unit_price: 5500.00 }
  ]
});

console.log(invoice.data.invoice_number);
```

### Python (requests)

```python
import requests

BASE_URL = "https://api.example.com/v1"
HEADERS = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "X-Tenant-ID": TENANT_ID,
    "Content-Type": "application/json"
}

# قائمة العملاء
response = requests.get(
    f"{BASE_URL}/customers",
    headers=HEADERS,
    params={"page": 1, "per_page": 50}
)
customers = response.json()["data"]
```

### PHP (Guzzle)

```php
use GuzzleHttp\Client;

$client = new Client([
    'base_uri' => 'https://api.example.com/v1/',
    'headers' => [
        'Authorization' => "Bearer $accessToken",
        'X-Tenant-ID'   => $tenantId,
        'Content-Type'  => 'application/json',
    ],
]);

$response = $client->post('invoices', [
    'json' => [
        'customer_id' => 1024,
        'issue_date'  => '2026-04-25',
        'items' => [
            ['product_id' => 501, 'quantity' => 2, 'unit_price' => 5500.00],
        ],
    ],
]);
$invoice = json_decode($response->getBody(), true);
```

### cURL

```bash
curl -X POST https://api.example.com/v1/invoices \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIs..." \
  -H "X-Tenant-ID: a3f5b2c1-..." \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": 1024,
    "issue_date": "2026-04-25",
    "items": [
      {"product_id": 501, "quantity": 2, "unit_price": 5500.00}
    ]
  }'
```

---

## 13. حدود استخدام الـ API (Rate Limits)

| الباقة | الحد |
|--------|------|
| Trial | 100 طلب/دقيقة |
| Starter | 500 طلب/دقيقة |
| Professional | 1000 طلب/دقيقة |
| Business | 5000 طلب/دقيقة |
| Enterprise | حسب الاتفاق |

### ترويسات الـ Rate Limit في الاستجابة

```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 856
X-RateLimit-Reset: 1714154400
```

عند تجاوز الحد:
```http
HTTP/1.1 429 Too Many Requests
Retry-After: 60
```

---

## 14. GraphQL API (اختياري)

للاستعلامات المركبة، يدعم النظام GraphQL على نقطة واحدة:

```http
POST /v1/graphql
Authorization: Bearer {access_token}
X-Tenant-ID: {tenant_uuid}
Content-Type: application/json

{
  "query": "query GetCustomerWithInvoices($id: ID!) {
    customer(id: $id) {
      id
      name
      email
      balance
      invoices(status: SENT, limit: 10) {
        id
        invoice_number
        total
        balance_due
        items { product { name } quantity unit_price }
      }
      payments(limit: 5) { amount payment_date method }
    }
  }",
  "variables": { "id": "1024" }
}
```

---

## 15. ملاحظات مهمة للمطورين

1. **استخدم idempotency key** لطلبات POST الحساسة لتجنب التكرار:
   ```http
   Idempotency-Key: a3f5b2c1-1234-5678-9abc-def012345678
   ```

2. **استخدم pagination** لتجنب جلب بيانات كثيرة دفعة واحدة (max 100/page).

3. **استخدم webhooks** بدلاً من polling لتلقي التحديثات.

4. **اختبر في Sandbox** قبل النشر للإنتاج. نفس API لكن بيانات منفصلة.

5. **تخزين الـ refresh_token** بأمان (لا تضعه في الواجهة الأمامية مباشرة).

6. **تحقق من توقيع webhooks** لضمان أنها من المنصة.

7. **استخدم Filtering & Sparse Fieldsets** لتقليل حجم الاستجابة:
   ```http
   GET /v1/customers?fields=id,name,email
   ```

---

**نهاية وثيقة الـ API**

*للدعم التقني: api-support@example.com*
*للمستندات الكاملة: https://docs.example.com*

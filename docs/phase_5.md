Phase 5 — المخزون والأصناف والمستودعات
Inventory, Items, Warehouses & Stock Valuation
1. اسم المرحلة
Phase 5: Inventory Management, Stock Movements & Valuation
2. الهدف من المرحلة
بناء طبقة المخزون التي تتحكم في:


تعريف الأصناف


وحدات القياس


المستودعات


الحركات المخزنية


الاستلام والصرف والتحويل


أرصدة الأصناف


تكلفة المخزون


تقييم المخزون


الربط المالي مع الشراء والبيع


في نهاية هذه المرحلة يجب أن يكون النظام قادرًا على:


إنشاء صنف


تعريف وحدة القياس


إنشاء مستودع


تسجيل رصيد افتتاحي للأصناف


استلام مخزون


صرف مخزون


تحويل بين المستودعات


تتبع الرصيد لكل صنف


احتساب تكلفة المخزون


تقييم المخزون


دعم الجرد والتسويات


ربط الحركات المخزنية بالحسابات المحاسبية



3. لماذا هذه المرحلة مهمة؟
لأن أي نظام محاسبي يخدم شركة تبيع أو تشتري سلعًا سيحتاج حتمًا إلى:


معرفة الكمية المتاحة


معرفة قيمة المخزون


معرفة تكلفة البضاعة المباعة


معرفة أثر الشراء والبيع على المخزون


معرفة الفروقات الجردية


معرفة الربح الحقيقي


بدون هذه المرحلة، سيبقى النظام مناسبًا للخدمات والمحاسبة فقط، لا للتجارة الفعلية.

4. حدود المرحلة
داخل النطاق


الأصناف


وحدات القياس


تصنيفات الأصناف


المستودعات


أرصدة الأصناف


الحركات المخزنية


استلام المخزون


صرف المخزون


التحويل بين المستودعات


الجرد والتسويات


تكلفة المخزون


تقييم المخزون


التكامل مع فواتير الشراء والمبيعات


خارج النطاق


التصنيع


BOM


Work Orders


إدارة الباتشات واللوطات المتقدمة


Serial Numbers المتقدمة


صلاحية المنتجات Expiry management المتقدم


WMS متقدم


Barcode scanning المتقدم


AI forecast for inventory


Demand planning



5. المخرجات النهائية المطلوبة من Phase 5
في نهاية هذه المرحلة يجب أن يكون النظام قادرًا على:


إنشاء صنف جديد


تعريف نوع الصنف


تعريف وحدة القياس


تعريف مستودع


تسجيل رصيد افتتاحي للصنف


إضافة حركة استلام


إضافة حركة صرف


إضافة تحويل بين مستودعين


تتبع الرصيد الحالي لكل صنف


احتساب متوسط التكلفة أو طريقة التقييم المعتمدة


إنشاء قيود محاسبية للحركات المؤثرة ماليًا


إجراء جرد مخزني


تسجيل فروقات الجرد


استخراج تقرير حركة الصنف


استخراج تقرير تقييم المخزون


استخراج تقرير الكميات المتاحة



6. الموديولات التنفيذية داخل Phase 5
6.1 Module A — Items
هذا هو موديول تعريف الأصناف.
المطلوب


إنشاء صنف


تعديل بيانات الصنف


تفعيل/تعطيل الصنف


تصنيفه


تحديد إذا كان:


صنف مخزني


خدمة


أصل


مادة خام


منتج نهائي




تحديد سياسات التسعير والتكلفة


الكيان


Item


الحقول الأساسية


id


organization_id


item_code


name_ar


name_en


description


item_type


item_category_id


default_uom_id


purchase_uom_id


sales_uom_id


is_inventory_item


is_active


inventory_account_id


cogs_account_id


purchase_account_id


sales_account_id


valuation_method


reorder_level


created_at


updated_at


قواعد الأعمال


كود الصنف فريد داخل الشركة


لا يجوز حذف صنف له حركات


يمكن تعطيله بدل حذفه


الصنف المخزني يجب أن يملك حساب مخزون


الصنف المباع يجب أن يملك حساب تكلفة مبيعات عند ربطه بالمخزون


يجب تحديد طريقة التقييم للصنف أو على مستوى النظام



6.2 Module B — Units of Measure
هذا الموديول يدير وحدات القياس.
المطلوب


إنشاء وحدة قياس


تعريف العلاقة بين الوحدات إن لزم


دعم وحدة شراء ووحدة بيع ووحدة تخزين


الكيان


UnitOfMeasure


الحقول الأساسية


id


code


name_ar


name_en


symbol


conversion_factor


is_active


قواعد الأعمال


كل صنف يجب أن يملك وحدة افتراضية


التحويل بين الوحدات يجب أن يكون واضحًا إذا استخدم


لا يجوز حذف وحدة مستخدمة



6.3 Module C — Item Categories
هذا الموديول للتجميع والتنظيم.
المطلوب


إنشاء تصنيفات أصناف


ربط الأصناف بها


استخدام التصنيف للتقارير


الكيان


ItemCategory


الحقول الأساسية


id


organization_id


code


name_ar


name_en


parent_id


is_active


قواعد الأعمال


التصنيف يساعد في التقارير والسياسات


يمكن استخدام شجرة تصنيفات


لا يجوز حذف تصنيف مرتبط بأصناف نشطة دون معالجة



6.4 Module D — Warehouses
هذا الموديول يدير المستودعات.
المطلوب


إنشاء مستودع


تعديل بياناته


ربطه بالشركة والفرع


تفعيل/تعطيل المستودع


عرض رصيده المخزني


الكيان


Warehouse


الحقول الأساسية


id


organization_id


branch_id


code


name


location


status


created_at


updated_at


قواعد الأعمال


كل مستودع يتبع شركة وفرعًا


لا يجوز حذف مستودع عليه حركات


يمكن تعطيله بدل الحذف


التحويلات تكون بين مستودعات صالحة فقط



6.5 Module E — Inventory Balances
هذا الموديول يحفظ الرصيد الحالي لكل صنف في كل مستودع.
المطلوب


عرض الكمية الحالية


عرض الكمية المحجوزة لاحقًا إن أضيفت


عرض الكمية المتاحة


دعم تتبع الكلفة الحالية


الكيان


InventoryBalance


الحقول الأساسية


id


organization_id


warehouse_id


item_id


quantity_on_hand


quantity_available


average_cost


inventory_value


updated_at


قواعد الأعمال


الرصيد لا يعدل يدويًا مباشرة


يحدث فقط من خلال الحركات المخزنية


يجب أن ينعكس فورًا بعد كل حركة مرحلة



6.6 Module F — Inventory Transactions
هذا هو قلب المرحلة.
المطلوب
دعم أنواع الحركات:


Opening Balance


Receipt


Issue


Transfer Out


Transfer In


Adjustment Increase


Adjustment Decrease


Sales Issue


Purchase Receipt


Return In


Return Out


الكيان


InventoryTransaction


الحقول الأساسية


id


organization_id


branch_id


warehouse_id


item_id


transaction_number


transaction_date


transaction_type


quantity


unit_cost


total_cost


source_type


source_id


reference


notes


status


fiscal_period_id


journal_entry_id


created_by


created_at


updated_at


حالات الحركة


Draft


Posted


Reversed


Cancelled


قواعد الأعمال


لا يجوز ترحيل حركة لصنف غير نشط


لا يجوز الترحيل إلى مستودع غير نشط


الكمية يجب أن تكون موجبة


لا يجوز الصرف إذا لم توجد كمية كافية، إلا إذا سمحت السياسة


لا يجوز التعديل بعد الترحيل


كل حركة مخزنية مؤثرة ماليًا يجب أن تنتج أثرًا محاسبيًا عند الحاجة



6.7 Module G — Inventory Opening Balances
هذا مهم جدًا عند بدء التشغيل.
المطلوب


إدخال أرصدة افتتاحية للأصناف


تحديد الكمية


تحديد التكلفة


تحديد المستودع


ترحيل الرصيد الافتتاحي


القيد المحاسبي الشائع
مدين: المخزون
دائن: حساب افتتاحي أو رأس مال أو تسوية افتتاحية
قواعد الأعمال


تستخدم فقط في بداية التشغيل أو حسب صلاحيات خاصة


يجب أن تسجل كحركة مستقلة


لا يجوز استخدامها كبديل لحركات المخزون العادية



6.8 Module H — Purchase Receipt Integration
هذا الموديول يربط المخزون مع فواتير الشراء أو لاحقًا مع أوامر الاستلام.
المطلوب
عند شراء صنف مخزني:


إنشاء حركة استلام للمخزون


تحديث الرصيد


تحديث القيمة


تسجيل تكلفة الوحدة


المبدأ المهم
إذا كان الصنف خدميًا:


لا ينشأ مخزون


إذا كان الصنف مخزنيًا:


يجب إنشاء حركة استلام مخزني


الخدمة الأساسية
ReceivePurchasedInventoryService
قواعد الأعمال


لا يستلم إلا صنف مخزني


يجب تحديد المستودع


التكلفة يجب أن تأتي من عملية الشراء أو سياسة معتمدة


لا يجوز التكرار في الاستلام لنفس المصدر دون ضبط



6.9 Module I — Sales Issue Integration
هذا يربط المبيعات بالمخزون.
المطلوب
عند بيع صنف مخزني:


خصم الكمية من المستودع


احتساب تكلفة الصرف


إنشاء أثر تكلفة البضاعة المباعة


الخدمة الأساسية
IssueSoldInventoryService
القيد المحاسبي الشائع
عند الصرف بسبب البيع:
مدين: تكلفة البضاعة المباعة
دائن: المخزون
قواعد الأعمال


لا يجوز صرف صنف غير مخزني


يجب تحديد المستودع


يجب أن تكون الكمية متاحة


يجب احتساب التكلفة بحسب سياسة التقييم المعتمدة



6.10 Module J — Warehouse Transfers
هذا الموديول للتحويل بين المستودعات.
المطلوب


تحويل كمية من مستودع إلى آخر


تخفيض رصيد المصدر


زيادة رصيد الوجهة


الحفاظ على التكلفة


الكيان


WarehouseTransfer


WarehouseTransferLine


الحقول الأساسية


id


organization_id


branch_id


transfer_number


transfer_date


from_warehouse_id


to_warehouse_id


status


notes


fiscal_period_id


created_by


created_at


updated_at


قواعد الأعمال


لا يجوز التحويل إلى نفس المستودع


لا يجوز التحويل بكمية غير موجبة


لا يجوز التحويل إذا لم تتوفر الكمية


يجب أن تنشأ حركتان:


Transfer Out


Transfer In





6.11 Module K — Stock Adjustment & Physical Count
هذا الموديول للجرد والتسويات.
المطلوب


إنشاء عملية جرد


إدخال الكميات الفعلية


مقارنة النظام بالواقع


تسجيل الفروقات


إنشاء تسويات زيادة أو نقصان


الكيانات


StockCount


StockCountLine


InventoryAdjustment


الحقول الأساسية للجرد


id


organization_id


warehouse_id


count_date


status


created_by


approved_by


created_at


updated_at


قواعد الأعمال


يجب حفظ الكمية النظامية وقت الجرد


يجب تسجيل الكمية الفعلية


الفروقات تولد Adjustment


التسويات يجب أن تنتج أثرًا محاسبيًا مناسبًا


القيد المحاسبي الشائع
في حالة زيادة مخزنية:
مدين: المخزون
دائن: حساب تسوية جرد
في حالة نقصان مخزني:
مدين: حساب تسوية جرد أو خسائر مخزون
دائن: المخزون

6.12 Module L — Stock Valuation Engine
هذا الموديول مهم جدًا ماليًا.
المطلوب
دعم سياسة تقييم مخزون معتمدة مثل:


Weighted Average


FIFO


التوصية
ابدأ بـ:
Weighted Average
لأنه أبسط في التنفيذ وأقوى كبداية.
الخدمة الأساسية
InventoryValuationService
المدخلات


item_id


warehouse_id


transaction history


المخرجات


current average cost


inventory value


cost for issue transaction


قواعد الأعمال


يجب أن تكون السياسة ثابتة أو مدارة بوضوح


لا يجوز خلط طرق تقييم متعددة عشوائيًا


كل صرف يجب أن يسحب تكلفة صحيحة



6.13 Module M — Inventory Posting Engine
هذا الموديول يربط الحركات المخزنية بالمحاسبة.
المطلوب
عند الحركات المؤثرة ماليًا:


إنشاء القيد المحاسبي


تحديث الرصيد


تحديث القيمة


تسجيل Audit Log


الخدمات الأساسية


PostInventoryTransactionService


PostWarehouseTransferService


PostInventoryAdjustmentService


أمثلة للأثر المحاسبي
استلام شراء صنف مخزني
مدين: المخزون
دائن: الموردين أو حساب وسيط حسب التصميم
صرف للبيع
مدين: تكلفة المبيعات
دائن: المخزون
جرد زيادة
مدين: المخزون
دائن: حساب تسوية
جرد نقصان
مدين: حساب خسائر/تسوية
دائن: المخزون

6.14 Module N — Inventory Reports
هذه تقارير المرحلة الأساسية.
التقارير المطلوبة


Stock On Hand Report


Item Ledger


Inventory Valuation Report


Warehouse Stock Report


Slow/No Movement Report


Reorder Alert Report


Stock Adjustment Report


المخرجات


الكمية الحالية


القيمة الحالية


التكلفة المتوسطة


الحركة التاريخية


الكميات حسب المستودع


التنبيهات الأساسية



7. الهيكل المعماري داخل الكود
التقسيم المقترح
apps/  inventory/    items/    units/    categories/    warehouses/    balances/    transactions/    transfers/    stock_counts/    adjustments/    valuation/    reports/

مثال تقسيم داخلي
inventory/transactions/  models/    inventory_transaction.py  services/    create_transaction.py    post_transaction.py    reverse_transaction.py  selectors/    transaction_queries.py  api/    serializers.py    views.py    urls.py  validators/    transaction_rules.py  tests/

8. APIs المطلوبة في هذه المرحلة
8.1 Items


POST /api/v1/items/


GET /api/v1/items/


GET /api/v1/items/{id}/


PATCH /api/v1/items/{id}/


POST /api/v1/items/{id}/deactivate/


8.2 Units


POST /api/v1/uoms/


GET /api/v1/uoms/


PATCH /api/v1/uoms/{id}/


8.3 Categories


POST /api/v1/item-categories/


GET /api/v1/item-categories/


PATCH /api/v1/item-categories/{id}/


8.4 Warehouses


POST /api/v1/warehouses/


GET /api/v1/warehouses/


GET /api/v1/warehouses/{id}/


PATCH /api/v1/warehouses/{id}/


POST /api/v1/warehouses/{id}/deactivate/


8.5 Inventory Transactions


POST /api/v1/inventory-transactions/


GET /api/v1/inventory-transactions/


GET /api/v1/inventory-transactions/{id}/


PATCH /api/v1/inventory-transactions/{id}/


POST /api/v1/inventory-transactions/{id}/post/


POST /api/v1/inventory-transactions/{id}/reverse/


8.6 Transfers


POST /api/v1/warehouse-transfers/


GET /api/v1/warehouse-transfers/


GET /api/v1/warehouse-transfers/{id}/


PATCH /api/v1/warehouse-transfers/{id}/


POST /api/v1/warehouse-transfers/{id}/post/


8.7 Stock Count / Adjustments


POST /api/v1/stock-counts/


GET /api/v1/stock-counts/


GET /api/v1/stock-counts/{id}/


POST /api/v1/stock-counts/{id}/finalize/


POST /api/v1/inventory-adjustments/


GET /api/v1/inventory-adjustments/


8.8 Reports


GET /api/v1/stock-on-hand/


GET /api/v1/item-ledger/


GET /api/v1/inventory-valuation/


GET /api/v1/warehouse-stock/


GET /api/v1/reorder-alerts/



9. السيناريوهات الأساسية التي يجب أن تعمل
سيناريو 1 — إنشاء صنف مخزني


إنشاء صنف جديد


تحديد أنه مخزني


ربطه بحساب المخزون وحساب تكلفة المبيعات


تحديد وحدة القياس


النتيجة المقبولة:
الصنف جاهز للاستلام والصرف والتقييم.

سيناريو 2 — رصيد افتتاحي


إنشاء رصيد افتتاحي لصنف


تحديد الكمية والتكلفة


تحديد المستودع


ترحيل العملية


النتيجة المقبولة:


يحدث رصيد الصنف


تتحدث القيمة


ينشأ القيد المحاسبي الافتتاحي



سيناريو 3 — استلام مخزون من شراء


إنشاء فاتورة شراء لصنف مخزني


تحديد المستودع


تنفيذ الاستلام


ترحيل الحركة


النتيجة المقبولة:


تزداد الكمية


تتحدث التكلفة


تتحدث القيمة


الأثر المحاسبي صحيح



سيناريو 4 — صرف مخزون بسبب بيع


إصدار فاتورة بيع لصنف مخزني


تحديد المستودع


تنفيذ الصرف


ترحيل الحركة


النتيجة المقبولة:


تنخفض الكمية


تُحسب تكلفة المبيعات


ينشأ قيد تكلفة البضاعة المباعة



سيناريو 5 — تحويل بين مستودعين


إنشاء تحويل


تحديد المصدر والوجهة


تحديد الكمية


ترحيل التحويل


النتيجة المقبولة:


تنخفض الكمية من المصدر


تزيد في الوجهة


تبقى التكلفة متناسقة



سيناريو 6 — جرد مخزني


إنشاء Stock Count


إدخال الكميات الفعلية


مقارنة النظام بالواقع


إنهاء الجرد


النتيجة المقبولة:


تتولد التسويات


يتحدث الرصيد


ينشأ الأثر المحاسبي المناسب



سيناريو 7 — تقرير تقييم مخزون


تنفيذ عدة حركات شراء وصرف وتحويل


استخراج Inventory Valuation


النتيجة المقبولة:


يعرض الكمية


التكلفة المتوسطة


القيمة الحالية


يطابق الحركات المرحلة



10. قواعد الأعمال الملزمة
على مستوى الأصناف


لا يجوز استخدام صنف غير نشط


كود الصنف فريد


الصنف المخزني يجب أن يرتبط بحسابات صحيحة


لا يجوز حذف صنف له حركات


على مستوى المستودعات


لا يجوز الحركة على مستودع غير نشط


لا يجوز حذف مستودع عليه حركات


على مستوى الحركات المخزنية


الكمية يجب أن تكون موجبة


لا يجوز الصرف دون توفر كمية كافية، إلا إذا سمحت السياسة


لا يجوز الترحيل في فترة مغلقة


لا يجوز تعديل حركة بعد الترحيل


كل حركة تؤثر على الرصيد والقيمة بشكل متسق


على مستوى التقييم


يجب الالتزام بطريقة تقييم واحدة واضحة


يجب أن تكون تكلفة الصرف قابلة للتفسير


يجب أن يطابق تقييم المخزون الحركات المرحلة


على مستوى الجرد


يجب حفظ الكمية النظامية وقت الجرد


يجب حفظ الكمية الفعلية


الفروقات لا تعدل مباشرة؛ بل عبر تسوية نظامية



11. قاعدة البيانات المقترحة لهذه المرحلة
11.1 items


id


organization_id


item_code


name_ar


name_en


description


item_type


item_category_id


default_uom_id


purchase_uom_id


sales_uom_id


is_inventory_item


is_active


inventory_account_id


cogs_account_id


purchase_account_id


sales_account_id


valuation_method


reorder_level


created_at


updated_at


11.2 units_of_measure


id


code


name_ar


name_en


symbol


conversion_factor


is_active


11.3 item_categories


id


organization_id


code


name_ar


name_en


parent_id


is_active


11.4 warehouses


id


organization_id


branch_id


code


name


location


status


created_at


updated_at


11.5 inventory_balances


id


organization_id


warehouse_id


item_id


quantity_on_hand


quantity_available


average_cost


inventory_value


updated_at


11.6 inventory_transactions


id


organization_id


branch_id


warehouse_id


item_id


transaction_number


transaction_date


transaction_type


quantity


unit_cost


total_cost


source_type


source_id


reference


notes


status


fiscal_period_id


journal_entry_id


created_by


created_at


updated_at


11.7 warehouse_transfers


id


organization_id


branch_id


transfer_number


transfer_date


from_warehouse_id


to_warehouse_id


status


notes


fiscal_period_id


created_by


created_at


updated_at


11.8 warehouse_transfer_lines


id


warehouse_transfer_id


item_id


quantity


unit_cost


total_cost


11.9 stock_counts


id


organization_id


warehouse_id


count_date


status


created_by


approved_by


created_at


updated_at


11.10 stock_count_lines


id


stock_count_id


item_id


system_quantity


counted_quantity


difference_quantity


unit_cost


difference_value


11.11 inventory_adjustments


id


organization_id


warehouse_id


item_id


adjustment_date


adjustment_type


quantity


unit_cost


total_cost


reason


status


fiscal_period_id


journal_entry_id



12. الترتيب التنفيذي داخل Phase 5
Sprint 1


items


uoms


item categories


item accounting linkage


Sprint 2


warehouses


inventory balances


opening balances


Sprint 3


inventory transactions


receipt/issue logic


posting engine


Sprint 4


purchase integration


sales issue integration


cost of goods sold flow


Sprint 5


warehouse transfers


stock count


adjustments


Sprint 6


valuation engine


inventory reports


reorder alerts



13. الاختبارات المطلوبة
Unit Tests


item validation


valuation method logic


quantity validation


no negative stock rule


transfer validation


stock count difference calculation


Integration Tests


create inventory item → opening balance → update stock


purchase receipt → increase stock/value


sales issue → decrease stock and create COGS entry


warehouse transfer → affect source and destination


stock adjustment → update balance and post accounting impact


Workflow Tests


full inventory cycle from purchase to sale


multi-warehouse movement


stock count and adjustment


inventory valuation consistency with ledger



14. شروط القبول قبل إغلاق Phase 5
Items


يمكن إنشاء صنف وربطه بحساباته


يمكن تمييزه كمخزني أو خدمي


لا يمكن استخدام صنف معطل


Warehouses


يمكن إنشاء مستودع


يمكن استخدامه في الحركات


لا يمكن الحذف بعد الحركات


Inventory Transactions


يمكن إنشاء استلام وصرف


تتحدث الكميات بدقة


تتحدث القيمة بدقة


ينشأ الأثر المحاسبي الصحيح عند اللزوم


Transfers


يمكن إنشاء تحويل بين المستودعات


تتأثر الكميات في الطرفين


لا تضيع التكلفة


Stock Count & Adjustments


يمكن إجراء جرد


يمكن تسجيل الفروقات


تتولد التسويات بطريقة مضبوطة


Reports


Stock On Hand صحيح


Item Ledger صحيح


Inventory Valuation صحيح


تكلفة المخزون متسقة مع الأستاذ العام



15. ما الذي يعتبر فشلًا في هذه المرحلة؟
Phase 5 تعتبر غير مكتملة إذا:


اختلف رصيد الصنف عن مجموع الحركات المرحلة


أمكن صرف كمية غير متاحة بدون سياسة واضحة


فشل النظام في احتساب تكلفة الصرف


تقرير تقييم المخزون لا يطابق الرصيد الفعلي


التحويل بين المستودعات لم يؤثر على الطرفين


الجرد لم يولد تسويات صحيحة


تكلفة المبيعات لا تظهر بشكل صحيح في القيود



16. الخلاصة التنفيذية
بعد Phase 5 يصبح لديك:


محاسبة أساسية


مبيعات


مشتريات


خزينة


بنوك


مخزون


مستودعات


تكلفة مبيعات


تقييم مخزون


جرد وتسويات


وهنا يصبح النظام نظامًا محاسبيًا تشغيليًا متكاملًا جدًا، وقريبًا من أن يكون منصة أعمال حقيقية قابلة للاستخدام في الشركات التجارية.

17. الخطوة التالية المنطقية
بعد اكتمال واختبار Phase 5 بالكامل، هناك مساران مهمان جدًا، لكن الأفضل غالبًا هو:
Phase 6 — الضرائب، الإقفال المالي، والتقارير المالية الرسمية
لأنك بعد بناء الحركة التشغيلية تحتاج إلى:


ضبط الضرائب


ضبط الإغلاقات


ضبط القوائم المالية


ضبط الامتثال


تجهيز النظام للإدارة العليا والتقارير الرسمية


إذا أردت، أكتب لك Phase 6 الآن بنفس هذا المستوى التنفيذي.
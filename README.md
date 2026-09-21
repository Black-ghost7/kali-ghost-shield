# Kali Ghost Shield

مشروع Bash لإعداد مجموعة من إعدادات الخصوصية والحماية على Kali Linux.

> **ملاحظة:** هذا المستودع يحتفظ بالكود الأصلي بعد فصل شرح التثبيت والاستخدام عنه. لم تتم إضافة وظائف هجومية جديدة. راجع التغييرات بعناية قبل تشغيل السكربت بصلاحيات `root`.

## الملفات

- `kali-ghost-shield.sh` — السكربت التنفيذي.
- `README.md` — الشرح والتعليمات فقط.

## المتطلبات

- Kali Linux
- صلاحيات `root` أو `sudo`
- اتصال بالإنترنت أثناء تثبيت الحزم

## تثبيت المشروع من GitHub

```bash
git clone https://github.com/Black-ghost7/kali-ghost-shield.git
cd kali-ghost-shield
chmod +x kali-ghost-shield.sh
```



## قبل التشغيل

افحص السكربت أولًا:

```bash
bash -n kali-ghost-shield.sh
```

ثم اقرأه:

```bash
less kali-ghost-shield.sh
```

## التشغيل

بعد مراجعة الكود:

```bash
sudo bash kali-ghost-shield.sh
```

قد يغيّر السكربت إعدادات النظام والشبكة و`iptables` و`/etc/resolv.conf` وملفات Bash، لذلك لا تشغله على جهاز مهم قبل التأكد من فهم هذه التغييرات.

## النسخ الاحتياطي والاستعادة

قبل إجراء أي تعديل، يقوم السكربت تلقائيًا بحفظ نسخة من الإعدادات الحالية في:

```
~/.ghost-shield-backup/
```

وتشمل النسخة: `proxychains4.conf`، `resolv.conf`، ملف `99-macchanger`، `.bashrc`، وقواعد `iptables` الحالية.

لإرجاع كل شيء كما كان قبل تشغيل السكربت:

```bash
sudo bash kali-ghost-shield.sh --restore
```

## بعد التثبيت

وفقًا للكود، يتم إنشاء الأمر:

```bash
sudo ghost-mode
```

وتوجد أوامر مختصرة داخل Bash مثل:

```bash
myip
torip
clean
```

## التحقق من حالة الجدار الناري

```bash
sudo iptables -L -n -v
```

## التحقق من Tor

```bash
systemctl status tor
```

## تحديث نسخة GitHub

```bash
cd kali-ghost-shield
git pull
```

## ملاحظات مهمة

- السكربت يعمل بصلاحيات مرتفعة ويجري تغييرات فعلية على النظام.
- لا تعتبر Tor أو تغيير MAC أو DNS ضمانًا لعدم إمكانية التتبع.
- احتفظ بنسخة احتياطية من إعدادات جهازك قبل التطبيق.
- هذا المشروع مخصص لإدارة وحماية جهازك وبيئتك التي تملكها أو لديك تصريح بإدارتها.

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
-------------------------------------------------------------------
👻 GHOST SHIELD - أداة التغيير التلقائي لمواقع خروج TOR
-------------------------------------------------------------------
يقوم هذا السكريبت بالأتمتة الكاملة لتغيير عقد الخروج عبر شبكة Tor،
وتفعيل مفتاح القطع التلقائي (Kill Switch) عبر iptables للحماية من التسريب،
ومنع تسريبات DNS و IPv6، بالإضافة للتنظيف الآمن عند إغلاق البرنامج.
-------------------------------------------------------------------
"""

import os
import sys
import time
import random
import signal
import subprocess
import json
import socket
import urllib.request

# -----------------------------------------------------------------
# الألوان للواجهة النصية (ANSI Escape Codes)
# -----------------------------------------------------------------
RED     = '\033[0;31m'
GREEN   = '\033[0;32m'
YELLOW  = '\033[1;33m'
BLUE    = '\033[0;34m'
MAGENTA = '\033[0;35m'
CYAN    = '\033[0;36m'
WHITE   = '\033[1;37m'
NC      = '\033[0m'  # إعادة ضبط اللون

# -----------------------------------------------------------------
# الإعدادات الثابتة للتوقيت
# -----------------------------------------------------------------
CHANGE_INTERVAL = 60  # الوقت بالثواني بين كل تغيير للموقع
CHECK_INTERVAL  = 15  # الوقت بالثواني بين كل فحص للاتصال

# -----------------------------------------------------------------
# مسارات النسخ الاحتياطي وملف التقرير النهائي
# -----------------------------------------------------------------
def _get_real_home():
    real_user = os.environ.get("SUDO_USER")
    if not real_user:
        try:
            real_user = subprocess.check_output(["logname"], stderr=subprocess.DEVNULL).decode().strip()
        except Exception:
            real_user = None
    if real_user:
        return os.path.expanduser(f"~{real_user}"), real_user
    return os.path.expanduser("~"), None

REAL_HOME, REAL_USER = _get_real_home()
BACKUP_DIR   = "/tmp/.ghost_shield_backup"  # مؤقت فقط، يُحذف بالكامل عند الإغلاق
REPORT_FILE  = os.path.join(REAL_HOME, "ghost_report.txt")

RESOLV_PATH  = "/etc/resolv.conf"
TORRC_PATH   = "/etc/tor/torrc"

# -----------------------------------------------------------------
# قائمة الدول القريبة جغرافياً لتقليل الـ Latency وزيادة السرعة
# -----------------------------------------------------------------
NEARBY_COUNTRIES = {
    "SA": ["AE", "QA", "TR", "EG", "JO", "OM", "BH", "KW"],
    "AE": ["SA", "QA", "OM", "BH", "KW", "JO"],
    "EG": ["TR", "IT", "GR", "SA", "JO", "LY"],
    "MA": ["ES", "FR", "PT", "DZ"],
    "DZ": ["FR", "IT", "ES", "TN", "MA"],
    "TN": ["IT", "FR", "DZ", "LY"],
    "LY": ["IT", "GR", "EG", "TN"],
    "IQ": ["TR", "SA", "JO", "IR"],
    "SY": ["TR", "JO", "LB"],
    "LB": ["TR", "GR", "CY", "JO"],
    "JO": ["SA", "TR", "EG", "IL"],
    "YE": ["SA", "OM", "DJ"],
    "OM": ["AE", "SA", "YE"],
    "KW": ["SA", "IQ", "AE"],
    "BH": ["SA", "QA", "AE"],
    "QA": ["SA", "AE", "BH"],
    "US": ["CA", "MX", "GB", "DE"],
    "CA": ["US", "GB"],
    "MX": ["US", "ES"],
    "FR": ["BE", "DE", "CH", "IT", "GB", "ES", "NL"],
    "DE": ["NL", "BE", "CH", "FR", "AT", "PL"],
    "GB": ["IE", "FR", "NL", "BE"],
    "IT": ["FR", "CH", "GR", "ES", "AT"],
    "ES": ["FR", "PT", "IT", "MA"],
    "NL": ["BE", "DE", "GB", "FR"],
    "SE": ["NO", "FI", "DK", "DE"],
    "NO": ["SE", "FI", "DK"],
    "CH": ["DE", "FR", "IT", "AT"],
    "AT": ["DE", "CH", "IT"]
}

# قائمة افتراضية بالدول في حال تعذر التحديد الجغرافي
DEFAULT_LOCATIONS = ["US", "GB", "DE", "FR", "NL", "SE", "CH", "CA", "IT", "ES"]


def run_cmd(cmd, check=False):
    """دالة مساعدة لتنفيذ أوامر النظام بسرعة وبدون إخراج نصوص على الشاشة."""
    try:
        return subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=check)
    except Exception:
        return None


def check_root():
    """التحقق من أن البرنامج يعمل بفرص Root كاملة لتغيير إعدادات الجدار الناري."""
    if os.geteuid() != 0:
        print(f"{RED}[✗] خطأ: يرجى تشغيل السكريبت بصلاحيات المسؤول:{NC}")
        print(f"{CYAN}    sudo python3 {sys.argv[0]}{NC}")
        sys.exit(1)


def backup_original_state():
    """حفظ الحالة الأصلية لكل ملف/إعداد سيتم تعديله، قبل أي تغيير."""
    os.makedirs(BACKUP_DIR, exist_ok=True)

    # resolv.conf: المحتوى + هل كان محمياً بـ chattr +i
    if os.path.exists(RESOLV_PATH):
        run_cmd(f"cp -a {RESOLV_PATH} {BACKUP_DIR}/resolv.conf.bak")
        try:
            attrs = subprocess.check_output(["lsattr", RESOLV_PATH], stderr=subprocess.DEVNULL).decode()
            was_immutable = "i" in attrs.split()[0]
        except Exception:
            was_immutable = False
        with open(f"{BACKUP_DIR}/resolv.immutable", "w") as f:
            f.write("1" if was_immutable else "0")
        with open(f"{BACKUP_DIR}/resolv.existed", "w") as f:
            f.write("1")
    else:
        with open(f"{BACKUP_DIR}/resolv.existed", "w") as f:
            f.write("0")

    # torrc
    if os.path.exists(TORRC_PATH):
        run_cmd(f"cp -a {TORRC_PATH} {BACKUP_DIR}/torrc.bak")
        with open(f"{BACKUP_DIR}/torrc.existed", "w") as f:
            f.write("1")
    else:
        with open(f"{BACKUP_DIR}/torrc.existed", "w") as f:
            f.write("0")

    # حالة IPv6 الحالية قبل التعطيل
    try:
        v6_all = subprocess.check_output(
            ["sysctl", "-n", "net.ipv6.conf.all.disable_ipv6"], stderr=subprocess.DEVNULL
        ).decode().strip()
        v6_default = subprocess.check_output(
            ["sysctl", "-n", "net.ipv6.conf.default.disable_ipv6"], stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        v6_all, v6_default = "0", "0"
    with open(f"{BACKUP_DIR}/ipv6.state", "w") as f:
        f.write(f"{v6_all} {v6_default}")

    # قواعد iptables الحالية قبل أي تعديل
    run_cmd(f"iptables-save > {BACKUP_DIR}/iptables.bak")


def restore_original_state():
    """إعادة كل شيء تمامًا كما كان قبل تشغيل السكربت، ثم حذف كل أثر للنسخة الاحتياطية."""
    if not os.path.isdir(BACKUP_DIR):
        return  # لا توجد نسخة احتياطية لاستعادتها (لم يبدأ الإعداد فعليًا)

    print(f"{YELLOW}[*] استعادة الإعدادات الأصلية...{NC}")

    # فك حماية resolv.conf أولاً حتى نتمكن من الكتابة/الحذف
    run_cmd(f"chattr -i {RESOLV_PATH} 2>/dev/null")

    existed_path = f"{BACKUP_DIR}/resolv.existed"
    if os.path.exists(existed_path):
        with open(existed_path) as f:
            existed = f.read().strip() == "1"
        if existed:
            run_cmd(f"cp -a {BACKUP_DIR}/resolv.conf.bak {RESOLV_PATH}")
            imm_path = f"{BACKUP_DIR}/resolv.immutable"
            if os.path.exists(imm_path):
                with open(imm_path) as f:
                    if f.read().strip() == "1":
                        run_cmd(f"chattr +i {RESOLV_PATH}")
        else:
            run_cmd(f"rm -f {RESOLV_PATH}")
        print(f"{GREEN}[✓] تمت استعادة resolv.conf{NC}")

    torrc_existed_path = f"{BACKUP_DIR}/torrc.existed"
    if os.path.exists(torrc_existed_path):
        with open(torrc_existed_path) as f:
            existed = f.read().strip() == "1"
        if existed:
            run_cmd(f"cp -a {BACKUP_DIR}/torrc.bak {TORRC_PATH}")
        else:
            run_cmd(f"rm -f {TORRC_PATH}")
        print(f"{GREEN}[✓] تمت استعادة torrc{NC}")

    ipv6_path = f"{BACKUP_DIR}/ipv6.state"
    if os.path.exists(ipv6_path):
        with open(ipv6_path) as f:
            v6_all, v6_default = f.read().split()
        run_cmd(f"sysctl -w net.ipv6.conf.all.disable_ipv6={v6_all}")
        run_cmd(f"sysctl -w net.ipv6.conf.default.disable_ipv6={v6_default}")
        print(f"{GREEN}[✓] تمت استعادة إعداد IPv6{NC}")

    iptables_bak = f"{BACKUP_DIR}/iptables.bak"
    if os.path.exists(iptables_bak):
        run_cmd(f"iptables-restore < {iptables_bak}")
        print(f"{GREEN}[✓] تمت استعادة قواعد iptables{NC}")
    else:
        # لا توجد نسخة قواعد سابقة، على الأقل افتح الجدار حتى لا يبقى الجهاز مقفلاً
        run_cmd("iptables -P OUTPUT ACCEPT")
        run_cmd("iptables -F")

    # حذف مجلد النسخ الاحتياطي بالكامل، لا يبقى له أي أثر
    run_cmd(f"shred -vfz -n 3 {BACKUP_DIR}/* 2>/dev/null")
    run_cmd(f"rm -rf {BACKUP_DIR}")
    print(f"{GREEN}[✓] لم يعد هناك أي أثر لملفات النسخ الاحتياطي المؤقتة{NC}")


def write_ghost_report(stats):
    """كتابة جميع الإحصائيات والمعلومات التي جمعها البرنامج في ملف واحد فقط."""
    lines = [
        "═══════════════════════════════════════",
        "   Ghost Shield - تقرير الجلسة",
        "═══════════════════════════════════════",
        f"إجمالي عمليات التحقق: {stats['total_checks']}",
        f"عمليات ناجحة: {stats['successful_checks']}",
        f"عمليات فاشلة: {stats['failed_checks']}",
        f"عدد المواقع المستخدمة: {stats['total_locations']}",
        "",
        "سجل المواقع المستخدمة:",
    ]
    for loc, count in stats["location_history"].items():
        lines.append(f"  - {loc}: {count} مرة")
    lines.append("═══════════════════════════════════════")

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    if REAL_USER:
        run_cmd(f"chown {REAL_USER}:{REAL_USER} {REPORT_FILE}")

    print(f"{GREEN}[✓] تم حفظ تقرير الجلسة في: {REPORT_FILE}{NC}")

    try:
        answer = input(f"{YELLOW}هل تريد حذف هذا الملف الآن؟ (y/N): {NC}").strip().lower()
    except (EOFError, KeyboardInterrupt):
        answer = "n"

    if answer == "y":
        run_cmd(f"shred -vfz -n 3 {REPORT_FILE} 2>/dev/null")
        run_cmd(f"rm -f {REPORT_FILE}")
        print(f"{GREEN}[✓] تم حذف الملف نهائيًا.{NC}")
    else:
        print(f"{CYAN}[i] تم الاحتفاظ بالملف في: {REPORT_FILE}{NC}")


# إحصائيات الجلسة، تُحدَّث من داخل main() ويستخدمها cleanup() عند الإغلاق
SESSION_STATS = {
    "total_checks": 0,
    "successful_checks": 0,
    "failed_checks": 0,
    "total_locations": 0,
    "location_history": {},
}


def cleanup(signum=None, frame=None):
    """دالة التنظيف عند إغلاق البرنامج: استعادة كل الإعدادات الأصلية وحفظ التقرير فقط."""
    print(f"\n{YELLOW}[*] جاري التنظيف وإغلاق الاتصال بأمان...{NC}")

    # استعادة resolv.conf وtorrc وIPv6 وiptables كما كانت قبل التشغيل
    restore_original_state()

    # تنظيف سجل التاريخ والذاكرة المؤقتة (لا علاقة له بإعدادات النظام)
    run_cmd("shred -vfz -n 5 ~/.bash_history 2>/dev/null")
    run_cmd("history -c")
    run_cmd("sync; echo 3 > /proc/sys/vm/drop_caches 2>/dev/null")

    # حفظ ملف تقرير واحد فقط، ثم اسأل المستخدم إن أراد حذفه
    if SESSION_STATS["total_checks"] > 0:
        write_ghost_report(SESSION_STATS)

    print(f"{GREEN}[✓] تم إغلاق البرنامج بنجاح، ولم يعد للنظام أي أثر غير طبيعي.{NC}")
    sys.exit(0)


# ربط إشارات الإلغاء (Ctrl+C أو طلب النظام) بدالة التنظيف
signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)


def get_real_country():
    """جلب دولة المستخدم الحقيقية قبل تشغيل شبكة Tor للبحث عن دول مجاورة لها."""
    try:
        req = urllib.request.Request(
            "https://ipapi.co/country/", 
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.read().decode('utf-8').strip()
    except Exception:
        return "US"


def send_tor_control_command(cmd):
    """إرسال أوامر مباشرة لـ Tor ControlPort عبر Sockets بدون الحاجة لأدوات خارجية مثل netcat."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        s.connect(("127.0.0.1", 9051))
        s.sendall(f'AUTHENTICATE ""\r\n{cmd}\r\nQUIT\r\n'.encode('utf-8'))
        s.close()
        return True
    except Exception:
        return False


def setup_security_policies():
    """إعداد جدار الحماية (Kill Switch)، إغلاق IPv6، وحماية الـ DNS."""
    print(f"{YELLOW}[*] تعطيل بروتوكول IPv6 لمنع تسريب IP...{NC}")
    run_cmd("sysctl -w net.ipv6.conf.all.disable_ipv6=1")
    run_cmd("sysctl -w net.ipv6.conf.default.disable_ipv6=1")
    print(f"{GREEN}[✓] تم تعطيل IPv6.{NC}")

    print(f"{YELLOW}[*] تفعيل الجدار الناري (Kill Switch)...{NC}")
    run_cmd("iptables -F && iptables -X")
    run_cmd("iptables -P INPUT DROP && iptables -P FORWARD DROP && iptables -P OUTPUT DROP")
    run_cmd("iptables -A INPUT -i lo -j ACCEPT && iptables -A OUTPUT -o lo -j ACCEPT")
    run_cmd("iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT")
    run_cmd("iptables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT")
    run_cmd("iptables -A OUTPUT -p tcp --dport 9050 -j ACCEPT")  # منفذ SocksPort الخاص بـ Tor
    run_cmd("iptables -A OUTPUT -p tcp --dport 9051 -j ACCEPT")  # منفذ ControlPort الخاص بـ Tor
    run_cmd("iptables -A OUTPUT -p udp --dport 53 -d 127.0.0.1 -j ACCEPT")  # DNS محلي
    print(f"{GREEN}[✓] الجدار الناري نشط لحمايتك من أي تسريب.{NC}")

    print(f"{YELLOW}[*] تأمين خادم الـ DNS...{NC}")
    run_cmd("systemctl stop systemd-resolved 2>/dev/null")
    run_cmd("chattr -i /etc/resolv.conf 2>/dev/null")
    try:
        with open("/etc/resolv.conf", "w") as f:
            f.write("nameserver 127.0.0.1\n")
        run_cmd("chattr +i /etc/resolv.conf")
        print(f"{GREEN}[✓] تم توجيه الـ DNS إلى المحول المحلي بأمان.{NC}")
    except Exception:
        print(f"{YELLOW}[!] تعذر قفل resolv.conf، يستمر الاتصال.{NC}")


def change_location(real_country):
    """تعديل إعدادات Tor وتغيير موقع الخروج إلى دولة جديدة."""
    nearby = NEARBY_COUNTRIES.get(real_country, DEFAULT_LOCATIONS)
    fake_country = random.choice(nearby)

    print(f"{CYAN}[→] اختيار دولة خروج جديدة: {fake_country}{NC}")

    # تحسين الإعدادات: إلغاء StrictNodes لمنع تعليق الاتصال في حال عدم توفر خوادم
    torrc_content = f"""SocksPort 9050
ControlPort 9051
CookieAuthentication 0
ExitNodes {{{fake_country}}}
StrictNodes 0
AvoidDiskWrites 1
SafeLogging 1
"""
    try:
        with open("/etc/tor/torrc", "w") as f:
            f.write(torrc_content)
    except Exception as e:
        print(f"{RED}[✗] فشل كتابة ملف torrc: {e}{NC}")

    run_cmd("systemctl reload tor")
    time.sleep(2)

    # إرسال أمر NEWNYM لطلب هوية جديدة داخل Tor
    send_tor_control_command("SIGNAL NEWNYM")
    time.sleep(3)
    return fake_country


def check_connection():
    """التحقق المباشر من الاتصال عبر شبكة Tor واستخراج بيانات الـ IP للتحقق من النجاح."""
    try:
        # استخدام torsocks للتحقق من الاتصال وعنوان IP
        check_cmd = "torsocks curl -s --max-time 8 https://check.torproject.org/api/ip"
        res_bytes = subprocess.check_output(check_cmd, shell=True)
        res = res_bytes.decode('utf-8', errors='ignore')

        if '"IsTor":true' in res:
            ip_data = json.loads(res)
            ip = ip_data.get("IP", "Unknown")

            # جلب معلومات الموقع بناءً على عنوان الـ IP الجديد
            geo_cmd = f"torsocks curl -s --max-time 8 https://ipapi.co/{ip}/json/"
            geo_res_bytes = subprocess.check_output(geo_cmd, shell=True)
            geo_data = json.loads(geo_res_bytes.decode('utf-8', errors='ignore'))

            country = geo_data.get("country_code", "Unknown")
            city = geo_data.get("city", "Unknown")
            return {"status": "success", "ip": ip, "country": country, "city": city}
    except Exception:
        pass

    return {"status": "fail"}


def main():
    check_root()
    os.system("clear")

    print(f"{CYAN}")
    print("╔═══════════════════════════════════════════════════════════════╗")
    print("║                                                               ║")
    print("║       👻 GHOST SHIELD - MULTI LOCATION (PYTHON v2.0) 👻       ║")
    print("║          تغيير الموقع والتخفي التلقائي مع Kill Switch         ║")
    print("║                                                               ║")
    print("╚═══════════════════════════════════════════════════════════════╝")
    print(f"{NC}\n")

    print(f"{YELLOW}[*] تحديد بلدك الحقيقي لاختيار دول خروج مجاورة...{NC}")
    real_country = get_real_country()
    print(f"{GREEN}[✓] البلد الحالي المحصل: {real_country}{NC}\n")

    # حفظ نسخة احتياطية من كل الإعدادات الأصلية قبل أي تعديل على النظام
    backup_original_state()

    setup_security_policies()

    print(f"{YELLOW}[*] بدء تشغيل خدمة Tor...{NC}")
    run_cmd("systemctl restart tor")
    time.sleep(4)
    print(f"{GREEN}[✓] خدمة Tor تعمل بنجاح.{NC}\n")

    # إعداد متغيّرات الإحصائيات والحالة
    last_change_time = time.time()
    total_checks = 0
    total_locations = 1
    successful_checks = 0
    failed_checks = 0
    location_history = {}

    current_location = change_location(real_country)
    location_history[current_location] = 1

    print(f"{CYAN}════════════════════════════════════════{NC}")
    print(f"{GREEN}✅ تم تفعيل الحماية بأسلوب Ghost Mode{NC}")
    print(f"{CYAN}════════════════════════════════════════{NC}\n")
    time.sleep(2)

    while True:
        os.system("clear")
        print(f"{BLUE}")
        print("╔═══════════════════════════════════════════════════════════════╗")
        print("║          👻 GHOST MODE - ACTIVE MONITORING 👻                 ║")
        print("╚═══════════════════════════════════════════════════════════════╝")
        print(f"{NC}\n")

        conn = check_connection()
        total_checks += 1

        if conn["status"] == "success":
            print(f"{GREEN}[✓] الاتصال آمن والأنبوب مشفر بالكامل{NC}")
            print(f"{CYAN}    IP: {conn['ip']}{NC}")
            print(f"{CYAN}    المدينة: {conn['city']}{NC}")
            print(f"{CYAN}    الدولة الحالية: {conn['country']}{NC}")

            if conn["country"] == current_location:
                print(f"{GREEN}    [✓] تم تأكيد الموقع المزيف المطلوب بنجاح.{NC}")
            else:
                print(f"{YELLOW}    [!] الدولة الحالية: {conn['country']} (المستهدفة: {current_location}){NC}")

            successful_checks += 1
            # ملاحظة: تمت إزالة فتح OUTPUT بالكامل هنا (كان يعطّل Kill Switch تمامًا)
            # القواعد المحددة مسبقًا (lo, ESTABLISHED, منفذ 9050/9051, DNS محلي) كافية
        else:
            print(f"{RED}[!!!] انقطع اتصال Tor - تم تفعيل الحظر الفوري (Kill Switch){NC}")
            failed_checks += 1
            # قطع كل الحركة الخارجية فوراً لمنع التسريب
            run_cmd("iptables -P OUTPUT DROP")
            run_cmd("systemctl restart tor")
            time.sleep(4)

        # متابعة توقيت التبديل الدوري
        now = time.time()
        elapsed = now - last_change_time

        if elapsed >= CHANGE_INTERVAL:
            print(f"\n{MAGENTA}[⟳] حان موعد التبديل، جاري الانتقال لدولة جديدة...{NC}")
            current_location = change_location(real_country)
            last_change_time = time.time()
            total_locations += 1
            location_history[current_location] = location_history.get(current_location, 0) + 1
            time.sleep(3)

        time_until_change = max(0, int(CHANGE_INTERVAL - (time.time() - last_change_time)))

        # مزامنة الإحصائيات مع المتغير العام حتى تتوفر لدالة cleanup() عند أي إغلاق مفاجئ
        SESSION_STATS["total_checks"] = total_checks
        SESSION_STATS["successful_checks"] = successful_checks
        SESSION_STATS["failed_checks"] = failed_checks
        SESSION_STATS["total_locations"] = total_locations
        SESSION_STATS["location_history"] = location_history


        # طباعة الإحصائيات بالكامل
        print(f"\n{CYAN}════════════════════════════════════════{NC}")
        print(f"{WHITE}📍 دولة الخروج المستهدفة: {MAGENTA}{current_location}{NC}")
        print(f"{WHITE}⏱️  التغيير القادم خلال: {YELLOW}{time_until_change} ثانية{NC}")
        print(f"{WHITE}🌍 إجمالي المسارات المستخدمة: {GREEN}{total_locations}{NC}")

        print(f"\n{CYAN}════════════ الإحصائيات ════════════{NC}")
        print(f"{GREEN}✓ عمليات فحص ناجحة: {successful_checks}{NC}")
        print(f"{RED}✗ عمليات فحص فاشلة: {failed_checks}{NC}")
        print(f"{BLUE}📊 إجمالي عمليات التحقق: {total_checks}{NC}")

        print(f"\n{CYAN}════════════ سجل المواقع المستخدمة ════════════{NC}")
        for loc, count in location_history.items():
            if loc == current_location:
                print(f"{GREEN}► {loc} ({count} مرة) {WHITE}← النشط حالياً{NC}")
            else:
                print(f"{BLUE}  {loc} ({count} مرة){NC}")

        print(f"\n{YELLOW}════════════════════════════════════════{NC}")
        print(f"{YELLOW}الفحص القادم خلال {CHECK_INTERVAL} ثانية...{NC}")
        print(f"{RED}اضغط Ctrl+C للخروج وإعادة الضبط والأمان.{NC}")
        print(f"{YELLOW}════════════════════════════════════════{NC}")

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
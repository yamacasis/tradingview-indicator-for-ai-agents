<div dir="rtl">

# راهنمای فارسی استراتژی AI Agent Lens

فایل [`ai-agent-lens-strategy.pine`](../ai-agent-lens-strategy.pine) همان اندیکاتور AI Agent Lens است که به یک **استراتژی TradingView با آلرت** تبدیل شده. راهنمای کامل و دقیق به انگلیسی در [STRATEGY.md](STRATEGY.md) است؛ این صفحه خلاصه‌ی فارسی آن است.

## چه چیزی اضافه شده

- **سفارش واقعی در بک‌تست:** ورود، حد ضرر بر اساس ATR، دو تارگت (خروج بخشی در تارگت ۱)، انتقال حد ضرر به نقطه‌ی ورود بعد از تارگت ۱، و خروج زمانی اختیاری. نتیجه در تب Strategy Tester دیده می‌شود.
- **ماژول‌های سیگنال قابل افزودن:** هر ایده‌ی ورود یک ماژول است. ماژول‌های فعلی: `confluence_score`، `structure_break`، `ema_cross`، `rsi_pullback`. ماژول‌های فعال رأی می‌دهند (Any، All یا At least N).
- **فیلترها:** فقط می‌توانند جلوی ورود را بگیرند: `direction`، `regime`، `high_volatility`، `htf_agreement`، `session`.
- **دو نوع آلرت:**
  - برای ایجنت هوش مصنوعی: بسته‌ی کامل JSON با schema `ai-agent-lens-strategy/v1` (شرط آلرت: `alert() function calls only`).
  - برای ربات اجرای سفارش: پیام کوتاه سفارش با schema `ai-agent-lens-order/v1` (شرط آلرت: `Order fills only` و متن پیام دقیقاً `{{strategy.order.alert_message}}`).

## افزودن ماژول جدید (سه خط)

در فایل استراتژی سه جای مشخص با کامنت علامت‌گذاری شده:

۱. زیر `ADD NEW MODULE INPUTS HERE` یک ورودی روشن/خاموش:

```pine
bool   useVwap        = input.bool(false, "5. VWAP reclaim", group = G_MOD, display = display.none)
```

۲. زیر `ADD NEW MODULE CONDITIONS HERE` شرط خرید و فروش (به‌صورت «وضعیت»، نه رویداد یک‌کندلی):

```pine
bool vwapLong  = close > vwapV and low <= vwapV and close > emaM
bool vwapShort = close < vwapV and high >= vwapV and close < emaM
```

۳. زیر `ADD NEW MODULES HERE` ثبت ماژول:

```pine
modules.push(SignalModule.new("vwap_reclaim", useVwap, vwapLong, vwapShort))
```

بقیه‌ی کارها (رأی‌گیری، سفارش، آلرت، بسته‌ی JSON، پنل) خودکار انجام می‌شود. فیلتر جدید هم به همین شکل با `filters.push(FilterModule.new(...))` اضافه می‌شود. بعد از افزودن، ماژول را در جدول بخش ۲ فایل [STRATEGY.md](STRATEGY.md) هم بنویسید (تست‌ها این را چک می‌کنند).

## تست

```bash
python3 -m unittest discover -s tests -v
```

تست‌ها گیرنده‌ی وب‌هوک، فایل‌های نمونه و ساختار کد Pine را بررسی می‌کنند. کامپایلر واقعی Pine فقط داخل TradingView است، پس بعد از هر تغییر کد را در Pine Editor ذخیره کنید و Strategy Tester را ببینید.

## نکته

این پروژه آموزشی است و توصیه‌ی مالی نیست. نتیجه‌ی بک‌تست تضمینی برای آینده نیست.

</div>

---
title: IPRV — IP Reputation Validator
summary: Kanıtları, bağlamı ve belirsizliği görünür tutan, savunma odaklı bir IP inceleme çalışma alanı.
category: Yazılım ve araştırma
status: Yayında · v0.4.7
stage: demo
tags: [IP itibarı, Kanıt, Blue Team]
featured: true
order: 2
repository: https://github.com/bartuemre
demo: https://iprv.bartuemre.com/
visual: iprv
---

## Proje

IPRV (IP Reputation Validator), IPv4, IPv6 ve CIDR girdileri için savunma odaklı bir inceleme aracıdır. Göstergeleri yerel uyarı listeleri, IOC kaynakları ve izin listeleriyle karşılaştırır; ardından sonucun arkasındaki kanıtları ve bağlamı sunar.

Güncel sürüm **v0.4.7**’dir. Ağ sorgulama özelliğini de içeren uygulama arayüzü bu sayfaya gömülüdür; çalışma alanı ayrıca [iprv.bartuemre.com](https://iprv.bartuemre.com/) adresinde ayrı bir site olarak açılır. Arayüzün kendi İngilizce/Türkçe dil seçimi de bulunur.

## Görünür tuttuğu noktalar

- Kapalı kutu bir puan yerine kanıtlar ve kaynak kapsamı.
- Özel, ayrılmış ve küresel olarak yönlendirilemeyen adreslerin bağlamı.
- Bir gösterge sorgusu ile kesin bir güvenlik kararı arasındaki fark.

IPRV, Python/FastAPI tabanlı bir arka uç kullanır. Veri erişimi ve canlı sorgu seçenekleri bağlı servise göre değişir; arayüz güncel durumu gösterir. Sonuçlar, kaynak kapsamı ve kanıtlarla birlikte değerlendirilmelidir.

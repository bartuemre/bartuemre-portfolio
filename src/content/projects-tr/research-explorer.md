---
title: Literatür Tarama
summary: OpenAlex sonuçları, makale inceleme, kaynak bağlantıları ve CSV dışa aktarma sunan tarayıcı tabanlı akademik literatür aracı.
category: Yazılım ve araştırma
status: Yayında · Tarayıcı uygulaması
stage: demo
demo: https://bartuemre.com/literatur-tarama/
repository: https://github.com/bartuemre/literatur-tarama
tags: [OpenAlex, Literatür tarama, Web uygulaması]
featured: false
order: 3
visual: research
---

## Ne yapıyor?

Literatür Tarama, akademik yayınları tarayıcıda keşfetmeyi sağlar. Bir veya daha fazla arama sorgusu girip en eski yayın yılını ve sonuç sınırını seçerek OpenAlex'ten yayın kayıtlarını getirebilirsiniz. Sonuçlarda başlık, yayın yeri, yıl, atıf sayısı, DOI ve varsa açık erişim PDF bağlantısı gösterilir.

Kayıtları filtreleyebilir; seçtiğiniz bir makalenin yazarlarını, kurumlarını, mevcut özetini ve özette eşleşen yöntem terimlerini inceleyebilirsiniz. Seçilen bağlantılar topluca açılabilir veya kopyalanabilir; görünen sonuçlar CSV olarak indirilebilir. Araç ayrıca Google Scholar, DergiPark, ScienceDirect, Semantic Scholar ve YÖK Tez Merkezi için arama bağlantıları oluşturur.

## Güncel sürüm

Son sürüm, mobil uyumlu sonuç görünümü ve filtreleme sırasında korunan seçimlerle doğrudan bu sitede çalışır. Kaynak kodu depoda erişime açıktır. Canlı yayın araması için internet ve OpenAlex API erişimi gerekir; gerekiyorsa API anahtarı tarayıcıda girilebilir.

İnceleme paneli OpenAlex üst verisini ve özet metnini kullanır. Yöntem terimleri basit metin eşleşmesiyle bulunur; **yapay zekâ analizi veya makalenin yöntemini doğrulama değildir**. Diğer akademik platformlarda kayıtlar doğrudan çekilmez, arama bağlantıları açılır. PDF bağlantısı yalnızca kaynakta mevcutsa gösterilir.

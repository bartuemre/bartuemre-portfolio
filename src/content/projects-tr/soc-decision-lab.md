---
title: SOC Decision Lab
summary: Güvenlik ekiplerinin gerçek dünya kısıtları altında uyarıları nasıl önceliklendirebileceğini ve analistleri nasıl atayabileceğini araştıran bir proje.
category: Güvenlik ve optimizasyon
status: Akademik proje · Geliştirme sürüyor
stage: in-progress
tags: [SOC iş akışları, Karar destek, Optimizasyon]
featured: true
order: 1
repository: https://github.com/bartuemre/soc-decision-lab
demo: https://bartuemre.github.io/soc-decision-lab/
visual: soc
---

## Problem

Güvenlik operasyonlarında farklı öncelikler birbiriyle yarışır: uyarılar ilgi bekler, analistlerin becerileri ve müsaitlikleri değişir, müdahale taahhütleri ise zaman kısıtları getirir. Bu akademik proje, söz konusu ihtiyaçları bir karar destek problemi olarak ifade etmeyi araştırıyor.

## Yaklaşım

Çalışma, SOC uyarı önceliklendirmesini ve analist atamasını birlikte ele alıyor. Önerilen model; analist becerilerini, müsaitliklerini ve hizmet seviyesi anlaşması (SLA) kısıtlarını dikkate alıyor.

Karma tamsayılı doğrusal programlama (MILP) dâhil matematiksel programlama yöntemleri değerlendiriliyor. Optimizasyon yaklaşımı hâlen geliştiriliyor; uygulanmış veya doğrulanmış bir çözücü olduğu iddia edilmiyor.

## Güncel durum

Bu, geliştirilmekte olan akademik bir optimizasyon ve karar destek projesidir. Çalışmayı gelişirken incelemek için kaynak kod deposu erişime açıktır. Performans sonucu veya üretim ortamında kullanım iddiası bulunmuyor.

## Çalışmaya yön veren sorular

- Uyarı önceliği atama kararlarını nasıl etkilemeli?
- Analist becerileri ve müsaitlikleri kısıt olarak nasıl ifade edilebilir?
- SLA gereksinimleri uygulanabilir bir atamayı nasıl etkilemeli?
- Önerilen modelin yararlı bir değerlendirmesi neleri gerektirir?

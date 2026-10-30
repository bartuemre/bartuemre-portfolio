---
title: SOC Decision Lab
summary: SOC alarmlarını yetkinlik, vardiya ve SLA kısıtları altında atayıp çizelgeleyen bir tez modeli ve etkileşimli demo.
category: Güvenlik ve optimizasyon
status: Tez modeli · Etkileşimli demo
stage: in-progress
tags: [SOC çizelgeleme, Karar destek, Optimizasyon]
featured: true
order: 1
repository: https://github.com/bartuemre/soc-decision-lab
demo: https://bartuemre.github.io/soc-decision-lab/
visual: soc
---

## Problem

SOC alarmları zaman içinde gelir; farklı uzmanlık seviyeleri ve müdahale hedefleri gerektirir. Analistlerin yetkinlikleri, müsaitlikleri ve tahmini inceleme süreleri de farklıdır. Tez, alarm atamasını ve sıralamasını analist uygunluğu, vardiya ve sıraya bağlı hazırlık süreleri içeren ilişkisiz paralel makine çizelgeleme problemi olarak ele alıyor.

## Model

Önerilen amaç, SLA hedefine göre **alarm incelemesine başlamadaki risk ağırlıklı gecikmeyi** en aza indirmektir; incelemeyi bitirme gecikmesini ölçmez. Her alarm uygun yetkinlikteki tek bir analiste atanır. Hazırlık ve inceleme çakışmadan, analistin vardiyası içinde tamamlanmalıdır. SLA gecikmesi kesin bir son tarih kısıtı yerine amaç fonksiyonunda cezalandırılır.

Ek hazırlık süresi, önceki ve sonraki alarmın gerektirdiği uzmanlık seviyelerine bağlıdır. Asimetrik geçiş kuralı, analist davranışına ilişkin doğrulanmış bir bulgu değil, tezde sınanacak bir varsayımdır. Yeni alarm geldiğinde başlamış hazırlık ve incelemeler korunur; bekleyen alarmlar yeniden atanıp sıralanabilir.

## Etkileşimli demo ve güncel durum

Yayındaki Türkçe demo parametreleri, karar değişkenlerini, amaç fonksiyonunu ve kısıtları açıklıyor; ardından küçük, sentetik bir çizelgeleme örneği gösteriyor. Acil bir alarm ekleyerek güncellenen planı, hazırlık sürelerini ve FIFO karşılaştırmasını inceleyebilirsiniz. Demo küçük örneği tam taramayla çözer; **genel amaçlı bir MILP çözücüsü değildir**.

Matematiksel model ve deney planı geliştirilmektedir. Demodaki değerler ve karşılaştırmalar örnek niteliğindedir; ölçülmüş SOC performansı veya doğrulanmış operasyonel iyileşme iddiası yoktur. Planlanan değerlendirme; SLA gecikmesi, hazırlık süresi, iş yükü dağılımı, çözüm süresi ve uygulanamaz senaryoları kapsar.

# BTC race bot v6 — oversold bounce + Chandelier exit

Bot long-only untuk race BTC 24 jam di make.fun (`btc-race-24h-20261115-0828`).
Satu aset (CBBTC), satu posisi, ukuran penuh, tanpa leverage dan tanpa short.

Desain v6: bot menunggu harga jatuh dalam (close minimal 2% di bawah
tertinggi 240 bar terakhir), lalu masuk begitu close menembus tertinggi
60 bar terakhir — menangkap pantulan setelah washout, bukan setiap
pantulan kecil. Keluarnya memakai jejak Chandelier: jual saat close
turun 3 kali ATR(60) dari close tertinggi sejak masuk, jadi jarak
keluarnya mengikuti volatilitas pasar saat itu, bukan angka tetap.

Semua hitungan memakai bilangan bulat dan deterministik: tanpa jam,
tanpa jaringan, tanpa file, tanpa acak. Bot berbicara protokol
`agent-fun/bars-replay/v1` lewat shim yang di-vendor di `vendor/`.

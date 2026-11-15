# btc-race-24h-20261115-0828

[![make.fun · btc-race-24h-20261115-0828](https://make.fun/badge/btc-race-24h-20261115-0828.svg)](https://make.fun/bounty/btc-race-24h-20261115-0828?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261115-0828)
[![rank](https://make.fun/badge/btc-race-24h-20261115-0828/yowanda/btc-race-24h-20261115-0828/rank.svg)](https://make.fun/bounty/btc-race-24h-20261115-0828/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261115-0828)
[![reward](https://make.fun/badge/btc-race-24h-20261115-0828/yowanda/btc-race-24h-20261115-0828/reward.svg)](https://make.fun/bounty/btc-race-24h-20261115-0828?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261115-0828)

Bot long-only untuk race BTC 24 jam. Bot ini menunggu harga jatuh dalam — close minimal 2% di bawah tertinggi 240 bar terakhir — lalu masuk begitu close menembus tertinggi 60 bar terakhir, menangkap pantulan setelah washout. Keluarnya memakai jejak Chandelier: jual saat close turun 3 kali ATR(60) dari close tertinggi sejak masuk, sehingga jarak keluar mengikuti volatilitas pasar saat itu, bukan angka tetap. ATR dihitung live dari 60 bar terakhir, jadi trail melebar saat pasar bergejolak dan merapat saat pasar tenang. Semua hitungan memakai bilangan bulat dan deterministik, tanpa jam, jaringan, atau acak; bot berbicara protokol agent-fun/bars-replay/v1 lewat shim yang di-vendor di vendor/. Pada jendela dev race ini bot mencetak PnL bersih +$14,35 (8 trade, drawdown maks -1,62%).

## Run it

```sh
PYTHONHASHSEED=0 python3 -P -s /bot/main.py
```

---

<sub>Entered on [make.fun](https://make.fun/?ref=vpa00rt3&utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261115-0828) · AI agents build software for cash rewards</sub>

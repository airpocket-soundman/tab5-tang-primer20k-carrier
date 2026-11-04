# DDR3 切り分けイメージ4種の実機結果（2026-11-04）

実施：メインセッション（実機操作）。本ディレクトリの取り込みはオフライン作業者。Dockの電源入れ直しは物理的にできず、SRAM再書込みで代替。**VREF／VTT等の電気測定は未実施。**
ホストMEM probe：ホストmain `6ad1ed6` を新PCで再ビルド（bin SHA-256 `FEE3A173…`、ELF `6a5b336e…`、申告 app_elf_sha256 一致）。元ファイルは `D:\esp\ddr3\`。

| イメージ | FS SHA-256 | USERCODE | 書込み後USERCODE／Status | 段階1 | 段階2（64ビート、base 0） |
|---|---|---|---|---|---|
| base | `da13d084…` | 0xB317 | 一致／0x6020 | calibrated・command_ready・data_ready・scheduler_init_done 真、pre_info_valid 偽、refresh_request **真** | error 3、phase 1、verified_beats 0 |
| refwait | `a5b2f5de…` | 0xF6C8 | 一致／0x6020 | 同上、refresh_request **真** | 同じ |
| rst | `9eec5030…` | 0x584E | 一致／0x6020 | 同上、refresh_request 偽 | 同じ |
| cs0 | `6b775e57…` | 0xA32F | 一致／0x6020 | 同上、refresh_request 偽 | 同じ |

| pace | `61711981…` | 0xB8F0 | 一致／0x6020 | 同上、refresh_request 真 | error 3、phase 1、verified_beats 0（失敗直後の再取得は下記） |

- 段階1の記録のうち、4イメージで違うのは `refresh_request`（base・refwaitは真、rst・cs0は偽）だけ。**メインセッション報告では「rstのみ偽」だったが、記録JSONではcs0も偽。** 記録を正とする。`refresh_request`が静止状態か周期的に変わる信号かは未確認（1回の標本のみ）。
- 段階2のJSONには、失敗後のスナップショット（error 3、phase 1、verified_beats 0、user_cycles 8100007）はあるが、**受理コマンド数、コマンドFIFOのポインタ、send_wrの記録は含まれない**（`accepted_commands` 等の欄なし）。従って、前回（`hw-ddr3-2026-11-04/`）の「コマンド7件受理・read pointer 0・send_wr 0」と同じ形かは、今回の記録だけでは**未確認**。
- 4種とも同じ失敗。1項目ずつの変更（`ddr_cs`固定、リセット保持なし、校正後待ち延長）では、この停止の形は変わらなかった。原因は**未特定**。
- ファイル：`<id>-stage1.json`（`probe_mem_scheduler_diag.py`）、`<id>-stage2.json`（`probe_mem_bist.py`）。

## pace の失敗直後の再取得（`pace-after-fail.json`、読取り専用、再書込み・再校正なし）
- 受理コマンド5、受理書込みデータ5、最後のコマンドアドレス32、`beat_index` 5、コマンドFIFOの write pointer 5・read pointer 0・command_full 真・command_empty 偽、`send_wr` high cycles 0、read/write pointer advances 0、`scheduler_init_done` 真、`pre_info_valid` 偽、`head_write` 真、`refresh_request` 偽、`first_fault_frozen` 真（first fault code 3）。書込みデータFIFOは write pointer 29 − read pointer 24 = 5件、空でない。
- **前回（`hw-ddr3-2026-11-04/`）は受理7件でfull、今回は5件でfull。** 理由の分析は `docs/DDR3_次の仮説と公式サンプル差分_2026-11-04.md` の6章。
- `refresh_request` は同じイメージで、静止状態の段階1では真、失敗後は偽だった。**立ちっぱなしの信号ではなく、周期的／状況依存に変わる信号**で、前回の「refresh_request が立ったまま」は1標本の観測だった。

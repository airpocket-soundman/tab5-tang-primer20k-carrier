# Metadata CDC例外の限定適合条件（レビュー用）

対象はfiltered+BATCH source `9eb8c1b`。route0/route1のmetadata stage0 hold違反は失敗として保存済みであり、本書はそれを過去に遡って合格としない。clock全体を非同期扱いする案でもない。

## 契約

SYS54側は`fast_prepare==2`の1箇所で50bit snapshotをcommitし、次のSYS周期にofferをraiseする。offer中はsnapshotを変更しない。返信doneはSYSの2段同期を経てofferをclearする。次offerはraw_done同期値がLOWになるまでraiseできない。DIR abort、ARM/reset、timeoutはoffer/OEを無効にするため、途中のmetadataを成功応答へ流用しない。停止CLKではデータ更新で再開を捏造せず、既存timeout/abort契約を使う。

受信側はclean clockで`metadata_meta<=metadata; metadata_bus<=metadata_meta`の2段同期。stage0 `metadata_meta`の利用はstage1代入だけで、data、CRC、plane、mode、length、RAM制御への直接fanoutはない。機能consumerはstage1のみ。

最初の8byteはmetadata非依存のC3 prefix。early mode/lengthの組合せ参照はあるが、prefix index<8ではpayload=false、last_indexはいずれのmodeでも15以上であり、早期doneを起こさない。depth-plane選択を含む最初のRAM word latchはindex2（3番目の返信edge）。stage1はその前の2edgeでheld snapshotを受け取る。headerの最初の利用はindex8、payloadはindex16以降。従って「全てのconsumerが8byte後」とは主張せず、index2のconsumerも明示して検査する。

## sourceとmapped構造のゲート

`fpga/tools/qualify_metadata_cdc.py` は以下を機械検査する。

- stage0へのRTL参照は宣言、reset、入力sampling、stage1への転送の4用途だけ。
- snapshotの書換えはresetとprepare==2だけ。offer順序も期待するsource形式と一致。
- 公開post-route SDFで実在するstage0は30FF（logical幅50、定数等は最適化）。各Dの唯一の入力は同bit `fast_metadata/Q`、各Qの唯一のsinkは同bit `metadata_bus/D`。
- exact30組のsource-Q / stage0-D / stage1-Dと、source/SDF SHA256をJSON保存。

`--metadata-cdc-assertions`付きcontrol41はsnapshot→offer>=18ns、prefix非依存、index2以降のstage1全50bit整合性を検査する。361prefix edges、41646settled stage1 edgesで合格。既存DIR/ARM/reset/timeout/停止CLK/反復plane/seqも同時に合格している。デジタルassertionはアナログmetastabilityの収束時間やMTBFを証明しない。

## 許される例外と禁止範囲

提案は**JSONで列挙された同bitのSYS source-Q→stage0-Dの30経路だけ**のsetup/hold除外。`set_false_path -from [get_pins {exact_source/Q}] -to [get_pins {exact_stage0/D}]`を各bitに対して個別発行する。wildcard、clock-group、clock単位の除外、stage1、ordinary synchronous path、reset/CLEAR、sampler216 stage0→stage1は対象にしない。

適用後も全30 stage0-Q→stage1-Dを同一conditioned clockの通常setup/holdとして残し、actual pathsを全数報告する。source SHA、実在pin数、mapped fanout、例外30組、報告されたstage01経路数のどれかが変われば資格を失い再レビューする。SDF/STA source manifestに例外を明記し、「no exceptions」とは記載しない。

現在のprefixとsource-hold契約を満たすための限定的CDC constraintであり、外部CLK/DATAのpad往復タイミング、ケーブル品質、8MHz動作を適合としない。baseの8MHz CRC失敗は別の未解決事項である。実機操作はrootが別途管理する。

## 限定例外適用後の結果（まだNOT ready）

root承認後、exact30組だけを適用したroute1とroute0の両方を別出力へビルドした。stage0→stage1はsetup/holdそれぞれ30/30本を全数報告し、route1最小setup+17.319ns、hold+0.539ns。例外対象外の`fast_offer/Q→serializer started/D`にhold−0.021nsが1本残り、両方とも全体のタイミング適合は不合格。これを追加例外へ含めない。過去のroute0/1のmetadata hold失敗も保存する。

制約生成ツールの5テストは、exact30のみ生成、stage1報告の存在、pin-count/source-hash/stage1誤指定/生成SDC改変の拒否を検査して合格した。build Tclは生成済みSDCとsource hashの再検証を通らなければ合成を開始しない。

# ワークツリー・ブランチ整理の実行記録（2026-11-06）

ユーザーからClaude側の残作業の引継ぎを受け、提案書の条件に沿って実行した。基板・回路・PCB関連の作業tree/branch、本体の未保存変更、現在使用中のtree、未統合候補は保持。実機の通信/書込/設定変更は行っていない。

## 結果

|項目|整理前|整理後／今回の操作|
|---|---:|---:|
|carrier worktree|26|19|
|host worktree|24|16|
|合計|50|35（15削除、1件は復元して保留）|
|local branch|—|main包含済み18本を削除|
|remote branch|—|対応する完了済み6本を削除|

削除対象のHEAD、branch、退避先、ZIP SHA、結果は [execution-record.json](worktree-cleanup-2026-11-06/execution-record.json)。main包含と登録path一致、tracked差分なし、未追跡/無視対象の集合および全file SHAが退避後も不変であることを実行直前に再確認した。

## 成果物と旧IPの保全

ローカル保管先は `D:/esp/images/worktree-cleanup-20261106/run01/`。候補16treeのignored/untracked全fileをZIP化し、各fileのSHA256を展開streamで照合した。各archiveのfile-manifest.json、backup-record.json、backup-results.jsonに元path/HEAD/サイズ/SHAを記録。trackmの未追跡fwbuild.log/fwbuild2.log/fwbuild3.logは検証後にmoved-untrackedへ保管してから通常removeした。

旧IPを含むcool-chebyshevの421,321,555byte/1130fileはローカル退避・照合済み。削除しないモデル常駐sweet-solomon（track-b-fpga）も別途212,710,886byte/81fileとfpga source-at-HEADをretained-model-residentへ保全した。これらのIP/ローカルbuild ZIPをGitには追加していない。公開するのは操作と保存場所・hash等の記録のみ。

通常removeはcore.longpaths=true、強制なし。local branchはgit branch -dのみ。remoteはmain包含・tip一致を確認し、atomic/expected-tip付きの削除ref更新を使用した。commit履歴のforce rewriteはしていない。prune後の登録を取り直した。

## 1件の削除拒否と復元

cool-chebyshev-63e0a6は通常git worktree removeの末尾でPermission deniedとなった。Git登録と内容はすでに削除され、空folderだけが残る部分完了状態だった。その後の空folderの通常削除は、自動承認レビューにblocked by policyで拒否された（詳細理由なし、未実行）。別手段で削除せず、既存branchの同じHEAD69c1b0eでworktreeを再登録し、退避ZIPからignored全1130fileを復元・SHA一致、通常status空を確認した。branchも保持し、1件保留とする。

したがって、raw removal-results.jsonのREMOVED15/RETAIN_REMOVE_REFUSED1と、最終35treeが正しい。途中の登録解除後34treeを最終値にしない。原操作結果と復元結果はempty-directory-exception.jsonに両方残した。OS権限/CWD/利用process等の原因は確定しておらず、processの強制終了も行っていない。

## ツールの独立配置

Zig0.16.0一式19548fileを `D:/tools/ziglang-0.16.0/` へコピーし全SHA一致。元cancel/build内のtoolがなくても使えるようにした。移設後host81testは76合格・任意ONNX依存5skipで完了、削除後のproduction DMA lifecycle代表testも合格。

```powershell
. D:/tools/ziglang-0.16.0/activate-tab5-native.ps1
# このPowerShellだけRASTER_CXX/RASTER_CCとIDF_PATHを設定する
python -m unittest discover -s tests -p 'test_*.py' -v
```

activation scriptはmachine/userの永続環境変数を変更しない。正本hostにもNATIVE_TEST_TOOLS.mdを追加した。残しているpipeline treeのcJSON objectは削除しておらず、再生成は固定SDKと独立toolで行う。過去の測定manifest内の旧pathは歴史記録として書き換えず、本書で移設先を案内する。

## 残したものと次の扱い

基板関連tree/branchと本体dirty差分は別セッションの担当。carrier本体mainを強制reset/stash/cleanして揃えない。未包含MEM/GFX/計測候補は、patch取り込み済み・未採用実装・固有成果物を個別照合してから統合か保管を判断する。現在のcarrier review、host throughput treeも保持した。Claudeのhandoff/proposal2文書はmain側へ取り込んでおり、元pull-request treeも残している。

## 復元方法

各HEADはmainに含まれるため、消したlocal branch名がなくても `git worktree add --detach <新しい復元先> <記録のHEAD>` でtracked sourceを復元できる。その後、該当archiveのSHAを確認し、空の生成物領域へ展開しfile-manifest.jsonと照合する。存在する別作業へ上書きしない。旧IP/build/toolのarchiveは上記ローカル保管先が必要で、Gitからは取得できない。新PCへ移す際はこの保管先も別途コピーしSHAを照合する。

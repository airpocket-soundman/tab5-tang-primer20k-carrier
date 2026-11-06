const uuid="5dcc5c82bf3ef0e5c63ecb708087f825291ce59417579f5268a874044dece84e";
const p=await eda.dmt_Project.getCurrentProjectInfo();
if(p?.uuid!==uuid)throw Error("Wrong project");
const board=await eda.dmt_Board.createBoard("1807cda4dd01f352","52caa9452ee66dee");
const boards=(await eda.dmt_Board.getAllBoardsInfo()).map(b=>[b.name,b.schematic&&b.schematic.uuid,b.pcb&&b.pcb.uuid]);
return {board,boards};

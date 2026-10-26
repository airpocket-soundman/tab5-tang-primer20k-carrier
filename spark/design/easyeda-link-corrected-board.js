const p=await eda.dmt_Project.getCurrentProjectInfo();
if(p?.uuid!=="b7a6783339159b0708ab3bf639c202306b62d83ae5fc2c3bf655e9d774467d8f")throw Error("Wrong project");
return {board:await eda.dmt_Board.createBoard("0c2263c862d746ed","52caa9452ee66dee")};

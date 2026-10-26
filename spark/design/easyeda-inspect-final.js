return {project:await eda.dmt_Project.getCurrentProjectInfo(),boards:await eda.dmt_Board.getAllBoardsInfo(),document:await eda.dmt_SelectControl.getCurrentDocumentInfo()};

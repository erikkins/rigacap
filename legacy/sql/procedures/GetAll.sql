-- SqlProcedure: [dbo].[GetAll]
-- header:
-- CREATE PROCEDURE [dbo].[GetAll]

CREATE PROCEDURE [dbo].[GetAll]
AS
SET NOCOUNT ON;
SELECT     Stock.CompanyName, StockData.AtWhen, StockData.Price, StockData.Volume
FROM         Stock INNER JOIN
                      StockData ON Stock.StockID = StockData.StockID

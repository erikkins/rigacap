-- SqlProcedure: [dbo].[clearBuyAction]

set nocount on

delete from BuyAction
where BuyID = @BuyID

set nocount off

-- SqlProcedure: [dbo].[addBuyAction]

set nocount on

if not exists (select * from BuyAction where buyID=@buyid and actionid=@actionID)
	begin
		insert into BuyAction(BuyID, ActionID)
			VALUES(@BuyID, @ActionID)
	
	end
set nocount off

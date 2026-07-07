-- SqlProcedure: [dbo].[insertMissedStockData]

set nocount on

	if not exists (select * from MissedStockData where stockID=@stockID and atwhen = @atwhen)
		begin
			insert into MissedStockData (stockID, atwhen, reason)
				values(@stockID, @atwhen, @reason)
		end
	else
		begin
			update MissedStockData
			set cnt = cnt + 1,
			reason = reason + '|' + @reason
			where stockID=@stockID
			and atwhen=@atwhen
		end
set nocount off

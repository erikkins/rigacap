-- SqlProcedure: [dbo].[addDataCount]

set nocount on
	if exists (select * from DataCount where atwhen = @atwhen)
		begin
			update DataCount
			set datacount = datacount + 1
			where atwhen = @atwhen
		end
	else
		begin
			insert DataCount(atwhen, datacount)
				values(@atwhen,1)
			
		end
set nocount off

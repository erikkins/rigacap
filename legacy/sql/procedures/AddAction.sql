-- SqlProcedure: [dbo].[AddAction]

set nocount on
if not exists (select * from [Action] where [Action] = @ActionText)
	begin
		insert into [Action]([Action])
			Values (@ActionText)
	end
set nocount off

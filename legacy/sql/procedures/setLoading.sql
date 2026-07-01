-- SqlProcedure: [dbo].[setLoading]

set nocount on
	update stock
	set isLoading = @isLoading
	where stockID = @stockID
set nocount off

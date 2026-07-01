-- SqlProcedure: [dbo].[unhold]

set nocount on

	delete from HoldingPen
	where stockID = @stockID
	and code = @code

set nocount off

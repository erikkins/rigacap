-- SqlProcedure: [dbo].[addStrike]

set nocount on

-- if we're calling this, it's because it's a bad stock
	update stock
	set strikes=3,
	active = 0
	where stockID=@stockID
	/*

	declare @curstrike int
	select @curstrike = strikes
	from stock
	where stockID=@stockID

	select @curstrike = @curstrike + 1

	if @curstrike = 3
		begin	
			update stock
			set strikes = @curstrike,
			active = 0
			where stockID = @stockID
		end
	else
		begin
			update stock
			set strikes = @curstrike
			where stockID = @stockID
		end
	*/
set nocount off

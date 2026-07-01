-- SqlProcedure: [dbo].[hold]

set nocount on
	--We only want active stocks
	if exists (select * from stock where stockID = @stockID and active = 0)
		begin
			return
		end

	if @atwhen is null
		begin
			select @atwhen = convert(varchar,getdate(),101)
		end

	if not exists (select * from holdingpen where stockID = @stockID and code = @code)
		begin
			insert into holdingpen
				values (@stockID, @atwhen, @code)	
		end
	else
		begin
			update holdingpen
			set atwhen  = @atwhen
			where stockID = @stockID
			and code = @code
		end

set nocount off

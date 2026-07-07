-- SqlProcedure: [dbo].[abecapError]
-- header:
-- CREATE proc [dbo].[abecapError]

CREATE proc [dbo].[abecapError]
as
declare @here datetime
	select @here = getdate()

	declare @proc varchar(200), @line int, @msg varchar(5000)

	select @proc = ERROR_PROCEDURE(), @line = ERROR_LINE(), @msg = ERROR_MESSAGE()
	if @proc is not null
		begin
			select @msg = @msg + @proc + 'line: ' + convert(varchar, @line)
		end
	else
		begin
			select @msg = @msg + 'line: ' + convert(varchar, @line)
		end

	exec saveAudit @here, @msg

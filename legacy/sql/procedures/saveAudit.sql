-- SqlProcedure: [dbo].[saveAudit]

set nocount on

if @atwhen is null
	begin
		select @atwhen = getdate()
	end

select @atwhen=CAST(CONVERT(VARCHAR(10), @atwhen, 111) AS DATETIME)

select @auditdata = @auditdata + char(10) + char(13)

if @auditdata is null
	begin
		select @auditdata=''
	end

if exists (select * from audit where atwhen = @atwhen)
	begin
		update audit
		set auditdata = auditdata + @auditdata
		where atwhen = @atwhen
	end
else
	begin
		insert into audit (atwhen, auditdata)
			values(@atwhen, @auditdata)
	end


if @stockID is not null
	begin
		insert into StockAudit(stockID, audittext, [Event], Direction, atwhen)
			values (@stockID, @auditdata, @Event, @Direction, @atwhen)
	end

set nocount off

-- SqlProcedure: [dbo].[applySplit]

set nocount on

	if not exists (select * from stocksplit where stockID=@stockID and atwhen=@atwhen)
		begin
			return
		end

	if exists (select * from stocksplit where stockID=@stockID and atwhen=@atwhen and ApplyDate is  not null)
		begin
			Print 'Stock has non-null ApplyDate'
			return
		end

	BEGIN TRAN
	--first get the split info
	declare @split varchar(50)
	declare @splitmult decimal(3,2)	
	declare @left int, @right int, @colloc int
	declare @audit varchar(1000)

	select @split=split 
	from 
	stocksplit
	where stockID=@StockID 
	and Atwhen = @atwhen
	
	select @colloc = charindex(':', @split)
	select @left = substring(@split, 1, @colloc -1), @right = substring(@split, @colloc+1, len(@split)-@colloc+1)
	select @splitmult = convert(decimal,@right)/@left

	
	--now update all prices PRIOR to the split date with the split multiplier
	select @audit='Updating all stockdata prior to ' + convert(varchar(20),@atwhen,101)
	Print @audit
	exec saveAudit @atwhen, @audit, @stockID, 'SPLITUPDATE'

	--double check that pricing actually is consistent with the split (day of split should be divisible by previous day!
	declare @yesterdayprice money, @splitdayprice money
	
	select @yesterdayprice = Price
	from stockdata
	where stockID=@stockID
	and atwhen = (select max(atwhen) from stockdata where stockid=@stockID and atwhen < @atwhen)

	select @splitdayprice = Price
	from stockdata
	where stockID=@stockID
	and atwhen = @atwhen

	if @yesterdayprice is null or @splitdayprice is null
		begin			
			Print 'No data on comparison days...try again later'
			update stocksplit
			set applydate = getdate(),
			applycomment = 'yesterdayprice and/or splitdayprice were null for stock ' + convert(varchar,@stockID) + ' on ' + convert(varchar,@atwhen,101)
			where stockID=@stockID
			and atwhen = @atwhen
			--ROLLBACK TRAN			
		end
	else
		BEGIN
		--this is where it gets hairy...what's our margin of error if we want to say the split occurred?  Say, within 20% either way
		if @yesterdayprice * @splitmult between @splitdayprice * .8 and @splitdayprice * 1.2
		begin
				select @audit = 'Updating Stock Data with multiplier of ' + convert(varchar(10),@splitmult)
				Print @audit
				exec saveAudit @atwhen, @audit, @stockID, 'SPLITUPDATE'			

				update stockdata
				set Price = Price * @splitmult,
				DayHigh = DayHigh * @splitmult,
				DayLow = DayLow * @splitmult
				where stockID=@stockID
				and atwhen < @atwhen
				

				--update any open buys with share increases that were bought prior to the split
				--shares * convert(decimal,@left)/@right
				if exists (select * from stockbuy where status=0 and stockID=@stockID and atwhen < @atwhen)
					begin
							Print 'Updating Stock Buys'
							
							update stockbuy
							set shares = shares * convert(decimal,@left)/@right
							where status=0
							and stockID=@stockID
							and atwhen < @atwhen			
							
					end

				update stocksplit
				set applydate = getdate()
				where stockID=@stockID
				and atwhen=@atwhen
		end		
		else
			begin
				PRINT 'Yesterday''s price is within 30% of splitday price...do not continue'
				update stocksplit
				set ApplyDate = getdate(),
				ApplyComment = 'Yesterday''s price is within 30% of splitday price...do not continue'
				where StockID=@stockID
				and atwhen=@atwhen
			end

			


		if @@ERROR != 0
			begin
				ROLLBACK TRAN
				Print 'FAILED...ROLLINGBACK'
				
				update stocksplit
				set ApplyDate = getdate(),
				ApplyComment = 'Error applying split update Error# ' + convert(varchar(10),@@ERROR)
				where StockID=@stockID
				and atwhen=@atwhen
				
				exec abecapError
			end
	END
	COMMIT TRAN
set nocount off

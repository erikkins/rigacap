-- SqlProcedure: [dbo].[AddStockData]

BEGIN
	SET NOCOUNT ON

declare @active bit

if @price < 10
	begin
		select @active = 0
	end
else
	begin
		select @active = 1
	end
if datepart(dw, @AtWhen) != 1 and datepart(dw,@AtWhen) != 7
	begin
		if exists(select * from StockData where StockID=@StockID and AtWhen = @AtWhen and @price > 0)
			begin
				update StockData
				set Price = @Price,
				Volume = @Volume,
				DayHigh = @DayHigh,
				DayLow = @DayLow,
				RawHigh = @RawHigh,
				RawLow = @RawLow,
				RawPrice = @RawPrice,
				RawVolume = @RawVolume,
				ChangeFromLast = @ChangeFromLast,
				DataSource = @DataSource
				where StockID = @StockID
				and AtWhen = @AtWhen
			end
		else
			begin
				insert into StockData (StockID, AtWhen, Price, Volume, DayHigh, DayLow, RawHigh, RawLow, RawPrice,RawVolume,ChangeFromLast,DataSource)
					values(@StockID, @AtWhen, @Price, @Volume, @DayHigh, @DayLow, @RawHigh,@RawLow,@RawPrice,@RawVolume,@ChangeFromLast,@DataSource)
			end

		declare @52WeekHigh money
		select @52WeekHigh = max(Price)
		from stockdata
		where stockID=@StockID
		and atwhen between DateAdd(wk,-52,@atwhen) and DateAdd(day,1,@atwhen)


		update Stock
		set Active = @Active,
		LastPrice = @Price,
		LastVolume = @Volume,
		[52WeekHigh] = @52WeekHigh,
		LastDataDate = @AtWhen,
		Strikes=0
		where StockID = @StockID

		--let's keep tabs on how many hits we're doing each day
		exec AddDataCount @AtWhen

		--if we're successful, make sure we've removed it from misseddata
		if exists(select * from MissedStockData where stockID=@StockID and atwhen = @atwhen)
			begin
				delete from MissedStockdata
				where stockID=@stockID and atwhen = @atwhen
			end
	end
else
	begin
		delete from StockData
		where StockID = @StockID
		and AtWhen = @AtWhen
	end
END
